import React, { useState } from 'react';
import Editor from '@monaco-editor/react';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../contexts/ThemeContext';
import { useToast } from '../contexts/ToastContext';
import logger from '../utils/logger';
import '../styles/ConfigViewer.css';

interface ConfigViewerProps {
  config: string;
  language?: string;
  readOnly?: boolean;
  onSave?: (newConfig: string) => void;
  title?: string;
}

const ConfigViewer: React.FC<ConfigViewerProps> = ({
  config,
  language = 'plaintext',
  readOnly = true,
  onSave,
  title
}) => {
  const { t } = useTranslation();
  const { theme } = useTheme();
  const toast = useToast();
  const [localConfig, setLocalConfig] = useState(config);
  const [isModified, setIsModified] = useState(false);
  const [editorMounted, setEditorMounted] = useState(false);
  const [wordWrap, setWordWrap] = useState<'off' | 'on'>('off');
  const editorRef = React.useRef<any>(null);

  // Map our theme to Monaco theme
  const getMonacoTheme = () => {
    if (theme === 'industrial' || theme === 'neumorphism') {
      return 'light';
    }
    return 'vs-dark';
  };

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      setLocalConfig(value);
      setIsModified(value !== config);
    }
  };

  const handleSave = () => {
    if (onSave && isModified) {
      onSave(localConfig);
      setIsModified(false);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([localConfig], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `config_${new Date().getTime()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(localConfig);
      toast.success(t('config_viewer.copied'));
    } catch (err) {
      logger.error('Failed to copy:', err);
    }
  };

  const handleEditorMount = (editor: any) => {
    editorRef.current = editor;
    setEditorMounted(true);
    // Manual layout on mount to avoid ResizeObserver issues
    setTimeout(() => {
      editor?.layout();
    }, 100);
  };

  const handleSearch = () => {
    // Trigger find dialog (Ctrl+F)
    if (editorRef.current) {
      editorRef.current.trigger('', 'actions.find');
    }
  };

  const toggleWordWrap = () => {
    setWordWrap(prev => prev === 'off' ? 'on' : 'off');
  };

  return (
    <div className="config-viewer">
      <div className="config-viewer-header">
        <h3>{title || t('config_viewer.default_title')}</h3>
        <div className="config-viewer-actions">
          <button onClick={handleSearch} className="btn-icon" title={t('config_viewer.search')}>
            🔍
          </button>
          <button
            onClick={toggleWordWrap}
            className="btn-icon"
            title={wordWrap === 'on' ? t('config_viewer.disable_word_wrap') : t('config_viewer.enable_word_wrap')}
            style={{ fontWeight: wordWrap === 'on' ? 'bold' : 'normal' }}
          >
            ⤸
          </button>
          <button onClick={handleCopy} className="btn-icon" title={t('config_viewer.copy')}>
            📋
          </button>
          <button onClick={handleDownload} className="btn-icon" title={t('config_viewer.download')}>
            ⬇️
          </button>
          {!readOnly && onSave && (
            <button
              onClick={handleSave}
              className="btn-primary"
              disabled={!isModified}
              title={t('config_viewer.save_changes')}
            >
              💾 {t('config_viewer.save')}
            </button>
          )}
        </div>
      </div>
      <div className="config-viewer-content">
        <Editor
          height="600px"
          language={language}
          value={localConfig}
          theme={getMonacoTheme()}
          onChange={handleEditorChange}
          onMount={handleEditorMount}
          options={{
            readOnly: readOnly,
            minimap: { enabled: true },
            fontSize: 14,
            lineNumbers: 'on',
            scrollBeyondLastLine: true,
            automaticLayout: false,
            wordWrap: wordWrap,
            folding: true,
            renderWhitespace: 'selection',
            padding: { top: 10, bottom: 10 },
            find: {
              addExtraSpaceOnTop: false,
              autoFindInSelection: 'never',
              seedSearchStringFromSelection: 'always',
            },
            quickSuggestions: false,
            suggest: { showWords: false },
            matchBrackets: 'always',
            bracketPairColorization: { enabled: true },
            glyphMargin: false,
          }}
        />
      </div>
      {isModified && (
        <div className="config-viewer-status">
          ⚠️ {t('config_viewer.unsaved_changes')}
        </div>
      )}
    </div>
  );
};

export default ConfigViewer;
