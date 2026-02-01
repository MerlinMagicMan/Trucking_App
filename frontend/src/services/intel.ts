/**
 * Intel API service (Phase 3D)
 */
import api from './api';
import type {
  IntelResponse,
  LaneIntelData,
  MarketIntelData,
  DestinationIntelData,
  NegotiationIntelData,
} from '../types/intel';

export const fetchLaneIntel = async (
  originGeohash: string,
  destinationGeohash: string,
  window = '6h',
): Promise<IntelResponse<LaneIntelData> | null> => {
  try {
    const res = await api.get<IntelResponse<LaneIntelData>>('/api/intel/lane', {
      params: { origin_geohash: originGeohash, destination_geohash: destinationGeohash, window },
    });
    return res.data;
  } catch {
    return null;
  }
};

export const fetchMarketIntel = async (
  marketGeohash: string,
  window = '6h',
): Promise<IntelResponse<MarketIntelData> | null> => {
  try {
    const res = await api.get<IntelResponse<MarketIntelData>>('/api/intel/market', {
      params: { market_geohash: marketGeohash, window },
    });
    return res.data;
  } catch {
    return null;
  }
};

export const fetchDestinationIntel = async (
  destinationGeohash: string,
  window = '6h',
): Promise<IntelResponse<DestinationIntelData> | null> => {
  try {
    const res = await api.get<IntelResponse<DestinationIntelData>>('/api/intel/destination', {
      params: { destination_geohash: destinationGeohash, window },
    });
    return res.data;
  } catch {
    return null;
  }
};

export const fetchNegotiationIntel = async (
  originGeohash: string,
  destinationGeohash: string,
  offeredRateUsd: number,
  window = '6h',
): Promise<IntelResponse<NegotiationIntelData> | null> => {
  try {
    const res = await api.get<IntelResponse<NegotiationIntelData>>('/api/intel/negotiation', {
      params: {
        origin_geohash: originGeohash,
        destination_geohash: destinationGeohash,
        offered_rate_usd: offeredRateUsd,
        window,
      },
    });
    return res.data;
  } catch {
    return null;
  }
};
