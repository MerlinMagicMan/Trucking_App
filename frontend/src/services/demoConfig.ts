/**
 * Demo Mode Configuration Store (DEMO-001)
 *
 * localStorage-backed configuration for demo mode settings.
 * All values stored under versioned key: demo_v1_config
 */

const CONFIG_KEY = 'demo_v1_config';

interface DemoConfig {
  demoMode: boolean;
  apiBaseUrl: string | null;
  adminOverride: boolean;
}

const DEFAULT_CONFIG: DemoConfig = {
  demoMode: true,
  apiBaseUrl: null,
  adminOverride: false,
};

function getConfig(): DemoConfig {
  try {
    const stored = localStorage.getItem(CONFIG_KEY);
    if (stored) {
      return { ...DEFAULT_CONFIG, ...JSON.parse(stored) };
    }
  } catch {
    // Ignore parse errors
  }
  return { ...DEFAULT_CONFIG };
}

function setConfig(updates: Partial<DemoConfig>): void {
  const current = getConfig();
  const updated = { ...current, ...updates };
  localStorage.setItem(CONFIG_KEY, JSON.stringify(updated));
}

// ---- Public API ----

export function getDemoMode(): boolean {
  return getConfig().demoMode;
}

export function setDemoMode(enabled: boolean): void {
  setConfig({ demoMode: enabled });
}

export function getApiBaseUrl(): string | null {
  return getConfig().apiBaseUrl;
}

export function setApiBaseUrl(url: string): void {
  setConfig({ apiBaseUrl: url || null });
}

export function getAdminOverride(): boolean {
  return getConfig().adminOverride;
}

export function setAdminOverride(enabled: boolean): void {
  setConfig({ adminOverride: enabled });
}

export function isApiConfigured(): boolean {
  const url = getApiBaseUrl();
  return url !== null && url.trim() !== '';
}

/**
 * Demo mode is active when:
 * - Explicitly enabled via toggle, OR
 * - No API URL is configured
 */
export function isDemoActive(): boolean {
  return getDemoMode() || !isApiConfigured();
}
