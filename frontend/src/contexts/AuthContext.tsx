/**
 * Authentication Context
 * Manages user authentication state and provides auth methods
 * Ensures proper JWT token handling throughout the application
 */

import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';
import axios from 'axios';
import APIService, { setTokens, clearTokens, isAuthenticated as checkAuth } from '../services/api.service';
import { User, AuthContextType, RegisterData, LoginTwoFactorRequiredError, TwoFactorRequiredResponse } from '../types';
import i18n from '../i18n/config';
import logger from '../utils/logger';

// Create context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Provider props
interface AuthProviderProps {
  children: React.ReactNode;
}

/**
 * Auth Provider Component
 * Wraps the application and provides authentication state
 */
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);

  /**
   * Apply language preference once the user loads. Theme preference is
   * applied by ThemeProvider itself (it reads `user` via useAuth() — see
   * ThemeContext.tsx) rather than through a window event bridge.
   */
  useEffect(() => {
    if (user?.preferred_language && user.preferred_language !== i18n.language) {
      i18n.changeLanguage(user.preferred_language);
    }
  }, [user]);

  /**
   * Load user data on mount if authenticated
   * Always attempt to load user - if HttpOnly cookie is valid, backend will authenticate
   */
  useEffect(() => {
    const loadUser = async () => {
      try {
        // Always try to load user (backend will check HttpOnly cookie)
        const userData = await APIService.users.getMe();
        setUser(userData);
        setIsAuthenticated(true);
      } catch (error) {
        // If 401/403, user is not authenticated (cookie expired or invalid)
        logger.debug('User not authenticated');
        clearTokens();
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    };

    loadUser();
  }, []);

  /**
   * Login function
   */
  const login = useCallback(async (email: string, password: string, twoFactorToken?: string, webauthnResponse?: object) => {
    try {
      const response = await APIService.auth.login(email, password, twoFactorToken, webauthnResponse);

      // Save tokens
      setTokens(response.access);

      // Set user data
      setUser(response.user);
      setIsAuthenticated(true);

      return response;
    } catch (error) {
      logger.error('Login failed:', error);

      // Check if 2FA is required
      if (axios.isAxiosError<TwoFactorRequiredResponse>(error) && error.response?.data?.two_factor_required) {
        const data = error.response.data;
        const twoFactorError: LoginTwoFactorRequiredError = {
          twoFactorRequired: true,
          message: data.message,
          totpAvailable: data.totp_available,
          webauthnOptions: data.webauthn_options,
        };
        throw twoFactorError;
      }

      throw error;
    }
  }, []);

  /**
   * Logout function
   */
  const logout = useCallback(async () => {
    try {
      await APIService.auth.logout();
    } catch (error) {
      logger.debug('Logout error:', error);
    } finally {
      clearTokens();
      setUser(null);
      setIsAuthenticated(false);
    }
  }, []);

  /**
   * Register function
   */
  const register = useCallback(async (data: RegisterData) => {
    try {
      const response = await APIService.auth.register(data);

      // Save tokens
      setTokens(response.access);

      // Set user data
      setUser(response.user);
      setIsAuthenticated(true);

      return response;
    } catch (error) {
      logger.error('Registration failed:', error);
      throw error;
    }
  }, []);

  /**
   * Update profile function
   */
  const updateProfile = useCallback(async (data: Partial<User>) => {
    try {
      const updatedUser = await APIService.users.updateProfile(data);
      setUser(updatedUser);
      return updatedUser;
    } catch (error) {
      logger.error('Profile update failed:', error);
      throw error;
    }
  }, []);

  /**
   * Refresh user data
   */
  const refreshUser = useCallback(async () => {
    try {
      const userData = await APIService.users.getMe();
      setUser(userData);
    } catch (error) {
      logger.error('Failed to refresh user:', error);
      throw error;
    }
  }, []);

  // Context value
  const value: AuthContextType = {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
    register,
    updateProfile,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

/**
 * Custom hook to use auth context
 */
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);

  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
};

export default AuthContext;
