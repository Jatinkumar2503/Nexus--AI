import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';

afterEach(() => vi.unstubAllGlobals());

describe('dashboard API lifecycle client', () => {
  it('posts a planner request to create a persisted plan', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 'plan-1' }) });
    vi.stubGlobal('fetch', fetchMock);
    await api.createLifecyclePlan({ disruption: { id: 'd1', node_id: null, edge_id: 'MUM->TNA', duration: 30, severity: 'HIGH', description: 'test', start_time: 0 }, trains: [], stations: [] });
    expect(fetchMock).toHaveBeenCalledWith('/api/planner/plans', expect.objectContaining({ method: 'POST' }));
  });

  it('uses a lifecycle plan ID for approval and commit', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'approved' }) });
    vi.stubGlobal('fetch', fetchMock);
    await api.approveLifecyclePlan('plan-1');
    await api.commitLifecyclePlan('plan-1');
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual([
      '/api/planner/plans/plan-1/approve',
      '/api/planner/plans/plan-1/commit',
    ]);
  });

  it('persists replay preferences and reads the replay timeline', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ preferences: { replay_speed: 2 } }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ events: [] }) });
    vi.stubGlobal('fetch', fetchMock);

    await api.setRecoveryPreferences({ simulation_speed: 30, replay_speed: 2 });
    await api.getReplayTimeline();

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/memory/preferences', expect.objectContaining({
      method: 'PUT', body: JSON.stringify({ preferences: { simulation_speed: 30, replay_speed: 2 } }),
    }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/replay/timeline');
  });
});
