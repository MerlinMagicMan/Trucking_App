/**
 * Live Mode Error Handling (Wave 3: B1)
 *
 * Centralized helpers for handling live-mode API errors gracefully.
 * Ensures consistent messaging when backend is unavailable.
 */

export interface LiveError {
  isLiveUnavailable: boolean;
  code?: string;
  message: string;
}

/**
 * Check if an error indicates the live API is unavailable
 */
export function isNotAvailableLive(err: unknown): boolean {
  if (!err) return false;

  // Network errors
  if (err instanceof TypeError && err.message.includes('fetch')) {
    return true;
  }

  // Axios-style errors
  const axiosErr = err as { code?: string; response?: { status?: number }; message?: string };
  if (axiosErr.code === 'ECONNREFUSED' || axiosErr.code === 'ERR_NETWORK') {
    return true;
  }
  if (axiosErr.response?.status === 503 || axiosErr.response?.status === 502) {
    return true;
  }
  if (axiosErr.message?.includes('Network Error')) {
    return true;
  }

  return false;
}

/**
 * Parse an error into a structured LiveError
 */
export function parseLiveError(err: unknown): LiveError {
  if (isNotAvailableLive(err)) {
    return {
      isLiveUnavailable: true,
      code: 'LIVE_UNAVAILABLE',
      message: 'Live API is unreachable. Using demo mode data.',
    };
  }

  const axiosErr = err as { response?: { data?: { detail?: string }; status?: number }; message?: string };

  if (axiosErr.response?.status === 404) {
    return {
      isLiveUnavailable: false,
      code: 'NOT_FOUND',
      message: 'Resource not found.',
    };
  }

  if (axiosErr.response?.status === 401 || axiosErr.response?.status === 403) {
    return {
      isLiveUnavailable: false,
      code: 'UNAUTHORIZED',
      message: 'Authentication required.',
    };
  }

  return {
    isLiveUnavailable: false,
    code: 'UNKNOWN',
    message: axiosErr.response?.data?.detail || axiosErr.message || 'An error occurred.',
  };
}

/**
 * User-friendly message for live unavailable state
 */
export const LIVE_UNAVAILABLE_MESSAGE = 'Live API is currently unreachable. The app is using demo data.';

/**
 * User-friendly message for live errors
 */
export function getLiveErrorMessage(err: unknown): string {
  const parsed = parseLiveError(err);
  return parsed.message;
}
