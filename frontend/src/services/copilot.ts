/**
 * Copilot API service (Phase 4)
 */
import api from './api';
import type { CopilotResponse } from '../types/copilot';

export const fetchPlanStatus = async (
  planId: string,
  params?: {
    window_lane?: string;
    window_market?: string;
    window_destination?: string;
    as_of?: string;
  },
): Promise<CopilotResponse | null> => {
  try {
    const res = await api.get<CopilotResponse>('/api/copilot/plan_status', {
      params: { plan_id: planId, ...params },
    });
    return res.data;
  } catch {
    return null;
  }
};
