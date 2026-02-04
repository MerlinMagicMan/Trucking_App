/**
 * Copilot API service (Phase 4 + 4.1 + 4.2)
 */
import api from './api';
import type {
  CopilotResponse,
  BranchPlanRequest,
  BranchPlanResponse,
  EvaluationHistoryItem,
  EvaluationReplayResponse,
} from '../types/copilot';

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

export const branchPlans = async (
  req: BranchPlanRequest,
): Promise<BranchPlanResponse | null> => {
  try {
    const res = await api.post<BranchPlanResponse>('/api/copilot/branch_plans', req);
    return res.data;
  } catch {
    return null;
  }
};

export const fetchEvaluationHistory = async (
  planId: string,
): Promise<EvaluationHistoryItem[]> => {
  try {
    const res = await api.get<EvaluationHistoryItem[]>('/api/copilot/evaluations', {
      params: { plan_id: planId },
    });
    return res.data;
  } catch {
    return [];
  }
};

export const replayEvaluation = async (
  evalId: number,
): Promise<EvaluationReplayResponse | null> => {
  try {
    const res = await api.get<EvaluationReplayResponse>(`/api/copilot/evaluations/${evalId}/replay`);
    return res.data;
  } catch {
    return null;
  }
};
