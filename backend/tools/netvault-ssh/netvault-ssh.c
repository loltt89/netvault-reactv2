/*
 * NetVault SSH Client
 * Native SSH v1 + v2 support via libssh
 *
 * Compile: gcc -o netvault-ssh netvault-ssh.c -lssh -ljson-c -O2
 * Or without json-c: gcc -o netvault-ssh netvault-ssh.c -lssh -O2 -DNO_JSON
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/time.h>
#include <sys/select.h>
#include <libssh/libssh.h>

#define MAX_OUTPUT 10*1024*1024  // 10MB max output
#define DEFAULT_TIMEOUT 10
#define DEFAULT_IDLE_MS 500

// Output modes
typedef enum {
    MODE_TEST,
    MODE_EXEC,
    MODE_SHELL
} RunMode;

// Global config
typedef struct {
    char *host;
    int port;
    char *user;
    char *pass;
    int timeout;
    int idle_ms;
    RunMode mode;
    char *commands;  // ||| separated
} Config;

// Result
typedef struct {
    int success;
    char *output;
    char *error;
} Result;

void print_json_result(Result *r) {
    // Escape JSON strings
    printf("{\"success\":%s", r->success ? "true" : "false");

    if (r->output && strlen(r->output) > 0) {
        printf(",\"output\":\"");
        for (char *p = r->output; *p; p++) {
            switch (*p) {
                case '"': printf("\\\""); break;
                case '\\': printf("\\\\"); break;
                case '\n': printf("\\n"); break;
                case '\r': printf("\\r"); break;
                case '\t': printf("\\t"); break;
                default:
                    if ((unsigned char)*p < 32) {
                        printf("\\u%04x", (unsigned char)*p);
                    } else {
                        putchar(*p);
                    }
            }
        }
        printf("\"");
    }

    if (r->error && strlen(r->error) > 0) {
        printf(",\"error\":\"");
        for (char *p = r->error; *p; p++) {
            switch (*p) {
                case '"': printf("\\\""); break;
                case '\\': printf("\\\\"); break;
                case '\n': printf("\\n"); break;
                case '\r': printf("\\r"); break;
                default: putchar(*p);
            }
        }
        printf("\"");
    }

    printf("}\n");
}

void result_error(const char *msg) {
    Result r = {0, NULL, (char*)msg};
    print_json_result(&r);
    exit(1);
}

void result_success(const char *output) {
    Result r = {1, (char*)output, NULL};
    print_json_result(&r);
    exit(0);
}

// Wait for data with timeout (returns 1 if data available, 0 if timeout, -1 on error)
int wait_for_data(ssh_channel channel, int timeout_ms) {
    struct timeval tv;
    tv.tv_sec = timeout_ms / 1000;
    tv.tv_usec = (timeout_ms % 1000) * 1000;

    fd_set fds;
    FD_ZERO(&fds);

    socket_t fd = ssh_get_fd(ssh_channel_get_session(channel));
    if (fd < 0) return -1;

    FD_SET(fd, &fds);

    int ret = select(fd + 1, &fds, NULL, NULL, &tv);
    return ret;
}

// Read all available data from channel (non-blocking)
// Filters out NULL bytes that some devices send
int read_available(ssh_channel channel, char *buffer, int max_len, int *total_read) {
    int nbytes;
    int pos = *total_read;
    char temp_buf[4096];

    while (pos < max_len - 1) {
        nbytes = ssh_channel_read_nonblocking(channel, temp_buf, sizeof(temp_buf) - 1, 0);
        if (nbytes < 0) {
            return -1;  // Error
        }
        if (nbytes == 0) {
            break;  // No more data
        }

        // Copy data filtering out NULL bytes
        for (int i = 0; i < nbytes && pos < max_len - 1; i++) {
            if (temp_buf[i] != '\0') {
                buffer[pos++] = temp_buf[i];
            }
        }

        // Check for --More-- paging
        buffer[pos] = '\0';
        if (strstr(buffer + pos - nbytes, "--More--") ||
            strstr(buffer + pos - nbytes, "-- More --")) {
            // Send space to continue
            ssh_channel_write(channel, " ", 1);
        }
    }

    *total_read = pos;
    buffer[pos] = '\0';
    return pos;
}

// Execute commands in shell mode with idle detection
char* run_shell_mode(ssh_session session, Config *cfg) {
    ssh_channel channel = ssh_channel_new(session);
    if (channel == NULL) {
        return strdup("Failed to create channel");
    }

    if (ssh_channel_open_session(channel) != SSH_OK) {
        ssh_channel_free(channel);
        return strdup("Failed to open channel");
    }

    // Request PTY with explicit terminal type and size
    if (ssh_channel_request_pty_size(channel, "xterm", 80, 24) != SSH_OK) {
        ssh_channel_close(channel);
        ssh_channel_free(channel);
        return strdup("Failed to request PTY");
    }

    // Start shell
    if (ssh_channel_request_shell(channel) != SSH_OK) {
        ssh_channel_close(channel);
        ssh_channel_free(channel);
        return strdup("Failed to start shell");
    }

    // Allocate output buffer
    char *output = malloc(MAX_OUTPUT);
    if (!output) {
        ssh_channel_close(channel);
        ssh_channel_free(channel);
        return strdup("Memory allocation failed");
    }
    output[0] = '\0';
    int output_len = 0;

    // Wait for initial prompt (idle detection)
    int idle_count = 0;
    int max_idle = 3;  // Number of idle cycles before considering prompt ready

    while (idle_count < max_idle && output_len < MAX_OUTPUT - 1) {
        int ret = wait_for_data(channel, cfg->idle_ms);
        if (ret > 0) {
            read_available(channel, output, MAX_OUTPUT, &output_len);
            idle_count = 0;  // Reset idle counter
        } else if (ret == 0) {
            idle_count++;  // Timeout - increment idle
        } else {
            break;  // Error
        }

        if (ssh_channel_is_eof(channel)) break;
    }

    // Execute commands
    if (cfg->commands && strlen(cfg->commands) > 0) {
        char *cmds = strdup(cfg->commands);
        char *cmd = strtok(cmds, "|||");

        while (cmd != NULL) {
            // Trim whitespace
            while (*cmd == ' ' || *cmd == '\t') cmd++;
            char *end = cmd + strlen(cmd) - 1;
            while (end > cmd && (*end == ' ' || *end == '\t')) *end-- = '\0';

            if (strlen(cmd) > 0) {
                // Send command
                char cmd_with_newline[4096];
                snprintf(cmd_with_newline, sizeof(cmd_with_newline), "%s\n", cmd);
                ssh_channel_write(channel, cmd_with_newline, strlen(cmd_with_newline));

                // Wait for response with idle detection
                idle_count = 0;
                while (idle_count < max_idle && output_len < MAX_OUTPUT - 1) {
                    int ret = wait_for_data(channel, cfg->idle_ms);
                    if (ret > 0) {
                        read_available(channel, output, MAX_OUTPUT, &output_len);
                        idle_count = 0;
                    } else if (ret == 0) {
                        idle_count++;
                    } else {
                        break;
                    }

                    if (ssh_channel_is_eof(channel)) break;
                }
            }

            cmd = strtok(NULL, "|||");
        }
        free(cmds);
    }

    // Send exit
    ssh_channel_write(channel, "exit\n", 5);
    usleep(100000);  // 100ms

    // Read any remaining output
    read_available(channel, output, MAX_OUTPUT, &output_len);

    ssh_channel_send_eof(channel);
    ssh_channel_close(channel);
    ssh_channel_free(channel);

    return output;  // Caller must free
}

// Execute single command via exec
char* run_exec_mode(ssh_session session, const char *command) {
    ssh_channel channel = ssh_channel_new(session);
    if (channel == NULL) {
        return strdup("Failed to create channel");
    }

    if (ssh_channel_open_session(channel) != SSH_OK) {
        ssh_channel_free(channel);
        return strdup("Failed to open channel");
    }

    if (ssh_channel_request_exec(channel, command) != SSH_OK) {
        ssh_channel_close(channel);
        ssh_channel_free(channel);
        return strdup("Failed to execute command");
    }

    char *output = malloc(MAX_OUTPUT);
    if (!output) {
        ssh_channel_close(channel);
        ssh_channel_free(channel);
        return strdup("Memory allocation failed");
    }

    int nbytes;
    int pos = 0;

    while ((nbytes = ssh_channel_read(channel, output + pos, MAX_OUTPUT - pos - 1, 0)) > 0) {
        pos += nbytes;
        if (pos >= MAX_OUTPUT - 1) break;
    }
    output[pos] = '\0';

    ssh_channel_send_eof(channel);
    ssh_channel_close(channel);
    ssh_channel_free(channel);

    return output;
}

int main(int argc, char *argv[]) {
    Config cfg = {
        .host = NULL,
        .port = 22,
        .user = NULL,
        .pass = "",
        .timeout = DEFAULT_TIMEOUT,
        .idle_ms = DEFAULT_IDLE_MS,
        .mode = MODE_SHELL,
        .commands = NULL
    };

    // Parse arguments
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-host") == 0 && i + 1 < argc) {
            cfg.host = argv[++i];
        } else if (strcmp(argv[i], "-port") == 0 && i + 1 < argc) {
            cfg.port = atoi(argv[++i]);
        } else if (strcmp(argv[i], "-user") == 0 && i + 1 < argc) {
            cfg.user = argv[++i];
        } else if (strcmp(argv[i], "-pass") == 0 && i + 1 < argc) {
            cfg.pass = argv[++i];
        } else if (strcmp(argv[i], "-timeout") == 0 && i + 1 < argc) {
            cfg.timeout = atoi(argv[++i]);
        } else if (strcmp(argv[i], "-idle") == 0 && i + 1 < argc) {
            cfg.idle_ms = atoi(argv[++i]);
        } else if (strcmp(argv[i], "-mode") == 0 && i + 1 < argc) {
            i++;
            if (strcmp(argv[i], "test") == 0) cfg.mode = MODE_TEST;
            else if (strcmp(argv[i], "exec") == 0) cfg.mode = MODE_EXEC;
            else if (strcmp(argv[i], "shell") == 0) cfg.mode = MODE_SHELL;
        } else if (strcmp(argv[i], "-cmds") == 0 && i + 1 < argc) {
            cfg.commands = argv[++i];
        }
    }

    if (!cfg.host || !cfg.user) {
        result_error("host and user are required");
    }

    // Initialize libssh
    ssh_session session = ssh_new();
    if (session == NULL) {
        result_error("Failed to create SSH session");
    }

    // Set options
    ssh_options_set(session, SSH_OPTIONS_HOST, cfg.host);
    ssh_options_set(session, SSH_OPTIONS_PORT, &cfg.port);
    ssh_options_set(session, SSH_OPTIONS_USER, cfg.user);
    ssh_options_set(session, SSH_OPTIONS_TIMEOUT, &cfg.timeout);

    // Enable SSH v1 and v2 (libssh auto-negotiates)
    // Note: SSH v1 support depends on libssh compile-time options

    // Disable strict host key checking
    int strict = 0;
    ssh_options_set(session, SSH_OPTIONS_STRICTHOSTKEYCHECK, &strict);

    // Allow legacy algorithms for compatibility with older devices
    // This includes ssh-rsa which some devices like Cisco ASA still use
    ssh_options_set(session, SSH_OPTIONS_HOSTKEYS,
        "ssh-ed25519,ecdsa-sha2-nistp521,ecdsa-sha2-nistp384,ecdsa-sha2-nistp256,"
        "rsa-sha2-512,rsa-sha2-256,ssh-rsa");
    ssh_options_set(session, SSH_OPTIONS_PUBLICKEY_ACCEPTED_TYPES,
        "ssh-ed25519,ecdsa-sha2-nistp521,ecdsa-sha2-nistp384,ecdsa-sha2-nistp256,"
        "rsa-sha2-512,rsa-sha2-256,ssh-rsa");

    // Connect
    int rc = ssh_connect(session);
    if (rc != SSH_OK) {
        char err[256];
        snprintf(err, sizeof(err), "Connection failed: %s", ssh_get_error(session));
        ssh_free(session);
        result_error(err);
    }

    // Try multiple authentication methods
    // 1. Try "none" auth first (some devices accept it)
    rc = ssh_userauth_none(session, NULL);
    if (rc == SSH_AUTH_SUCCESS) {
        goto auth_success;
    }

    // 2. Try password auth
    rc = ssh_userauth_password(session, NULL, cfg.pass);
    if (rc == SSH_AUTH_SUCCESS) {
        goto auth_success;
    }

    // 3. Try keyboard-interactive (for SSH v1 compatibility)
    rc = ssh_userauth_kbdint(session, NULL, NULL);
    if (rc == SSH_AUTH_INFO) {
        // Answer the prompts
        int nprompts = ssh_userauth_kbdint_getnprompts(session);
        for (int i = 0; i < nprompts; i++) {
            ssh_userauth_kbdint_setanswer(session, i, cfg.pass);
        }
        rc = ssh_userauth_kbdint(session, NULL, NULL);
    }
    if (rc == SSH_AUTH_SUCCESS) {
        goto auth_success;
    }

    // All methods failed
    {
        char err[256];
        snprintf(err, sizeof(err), "Authentication failed: %s", ssh_get_error(session));
        ssh_disconnect(session);
        ssh_free(session);
        result_error(err);
    }

auth_success:

    // Execute based on mode
    char *output = NULL;

    switch (cfg.mode) {
        case MODE_TEST:
            ssh_disconnect(session);
            ssh_free(session);
            result_success("Connection successful");
            break;

        case MODE_EXEC:
            if (!cfg.commands) {
                ssh_disconnect(session);
                ssh_free(session);
                result_error("cmds required for exec mode");
            }
            output = run_exec_mode(session, cfg.commands);
            break;

        case MODE_SHELL:
            output = run_shell_mode(session, &cfg);
            break;
    }

    ssh_disconnect(session);
    ssh_free(session);

    if (output) {
        // Check if output is an error message
        if (strncmp(output, "Failed", 6) == 0 || strncmp(output, "Memory", 6) == 0) {
            Result r = {0, NULL, output};
            print_json_result(&r);
            free(output);
            exit(1);
        }
        result_success(output);
        free(output);
    }

    return 0;
}
