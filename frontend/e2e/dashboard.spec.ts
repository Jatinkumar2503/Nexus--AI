import { expect, test } from '@playwright/test';

const disruption = {
  id: 'DIS-DEMO', edge_id: 'MUM->TNA', node_id: null, duration: 45,
  severity: 'HIGH', description: 'Track circuit signal failure', start_time: 0,
};
const plan = {
  recommended_strategy: 'reroute', confidence_score: 91,
  primary_reasoning: 'A safe detour protects priority passengers.',
  actions: [], is_mock_response: false,
  expected_metrics: { delay_minutes: 18, energy_kwh: 120, crew_violations: 0, resilience_score: 88 },
  planner_metadata: { mode: 'local', provider: 'local', execution_time_ms: 4, tool_calls: 0 },
  alternative_strategies: [{ strategy: 'hold', rationale: 'Retain corridor order', tradeoff: 'Higher passenger delay', rank: 2 }],
  risk_factors: ['Blocked corridor'], assumptions: ['Detour capacity is available'],
  uncertainties: [], recovery_timeline_minutes: [0, 10, 30],
};

test.beforeEach(async ({ page }) => {
  let injected = false;
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const simulationState = {
      simulation_time: '10:00:00', trains: [], stations: [],
      active_disruptions: injected ? [disruption] : [],
      metrics: { total_passenger_delay_minutes: 0, total_energy_kwh: 0, crew_violation_count: 0, resilience_score: 100 },
      negotiation_logs: [],
    };
    if (method === 'POST' && path.includes('/presets/') && path.endsWith('/inject')) injected = true;
    const body = path === '/api/simulation/state' ? simulationState
      : path === '/api/topology' ? { status: 'success', nodes: {}, edges: [] }
      : path === '/api/planner/status' ? { mode: 'local', model: 'gpt-5', enhanced_available: false, is_mock_response: false }
      : path === '/api/memory/outcomes' ? { outcomes: [] }
      : path === '/api/memory/preferences' ? { preferences: {} }
      : path === '/api/replay/timeline' ? { events: [{ stage: 'commit', message: 'Reroute committed', timestamp: '10:01:00' }] }
      : path === '/api/scenarios/compare' ? { status: 'success', scenarios: [{ id: 'reroute', name: 'Reroute', description: 'Safe detour', delay_minutes: 18, energy_cost_kwh: 120, crew_violations_count: 0, is_legal: true, resilience_score: 88, explainer: 'VB-20901 uses a safe detour', is_pareto_optimal: true }] }
      : method === 'POST' && path === '/api/planner/plans' ? { id: 'PLAN-1', plan, status: 'proposed' }
      : method === 'POST' && path.endsWith('/validate') ? { id: 'PLAN-1', plan, status: 'validated', validation: { is_valid: true, validated_strategy: 'reroute', findings: [] } }
      : method === 'POST' && path.endsWith('/approve') ? { id: 'PLAN-1', plan, status: 'approved' }
      : method === 'POST' && path.endsWith('/commit') ? { id: 'PLAN-1', plan, status: 'committed' }
      : { status: 'success', disruption };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
});

test('loads the dispatcher cockpit without a live backend', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('SYSTEM NORMAL')).toBeVisible();
  await expect(page.getByText('CORRIDOR SAFETY COCKPIT')).toBeVisible();
  await expect(page.getByText('LOCAL RULE ENGINE')).toBeVisible();
  await expect(page.getByTitle('Load Recovery Replay Timeline')).toBeVisible();
});

test('supports inject, plan, validate, and dispatcher approval', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'INJECT INCIDENT' }).click();
  await page.getByRole('button', { name: 'signal failure' }).click();
  await expect(page.getByText('DISRUPTION DETECTED')).toBeVisible();
  await page.getByRole('button', { name: 'GENERATE & VALIDATE PLAN' }).click();
  await expect(page.getByText('RISK & CONFIDENCE')).toBeVisible();
  await expect(page.getByText(/91% confidence/)).toBeVisible();
  await expect(page.getByText(/ALTERNATIVES:/)).toBeVisible();
  await page.getByRole('button', { name: 'DISPATCHER APPROVE' }).click();
  await expect(page.getByText('APPROVED: reroute')).toBeVisible();
  await page.getByRole('button', { name: 'Commit Strategy' }).click();
  await expect(page.getByRole('button', { name: 'Strategy Active' })).toBeVisible();
  await page.getByTitle('Load Recovery Replay Timeline').click();
  await expect(page.getByLabel('Replay position')).toBeVisible();
});
