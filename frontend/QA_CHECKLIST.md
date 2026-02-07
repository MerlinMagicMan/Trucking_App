# QA Checklist (Wave 3: Internal Release Gate)

## C1: Route + Refresh Matrix

All routes must work correctly on hard refresh (F5/Cmd+R):

| Route | Description | Status |
|-------|-------------|--------|
| `/plans` | Preflight plan generation | [x] SPA rewrite configured |
| `/routes` | Route data management | [x] SPA rewrite configured |
| `/trucks` | Truck fleet management | [x] SPA rewrite configured |
| `/plans/history` | Plan generation history | [x] SPA rewrite configured |
| `/snapshot` | Snapshot generator | [x] SPA rewrite configured |
| `/recommendations` | Recommendation display | [x] SPA rewrite configured |
| `/forward-look` | Forward projections | [x] SPA rewrite configured |
| `/intel` | Lane/market intelligence | [x] SPA rewrite configured |
| `/copilot` | AI plan status | [x] SPA rewrite configured |
| `/reports` | Analytics reports | [x] SPA rewrite configured |
| `/admin` | Admin console | [x] SPA rewrite configured |
| `/settings` | App settings | [x] SPA rewrite configured |
| `/maintenance` | Maintenance tracking | [x] SPA rewrite configured |

**Vercel Configuration**: `vercel.json` contains:
```json
{ "rewrites": [{ "source": "/(.*)", "destination": "/" }] }
```

## C2: Determinism Matrix

Same seed + same inputs must produce identical outputs:

| Function | Deterministic | Notes |
|----------|---------------|-------|
| `generateRecommendations()` | [x] Yes | Pure function, no randomness |
| `generateProjections()` | [x] Yes | Math.round only, no randomness |
| `generateLaneInsights()` | [x] Yes | Pure function, no randomness |
| Demo data generation | [x] Yes | crypto.randomUUID() only for IDs |
| Plan generation (demo) | [x] Yes | Deterministic based on inputs |
| Intel data (demo) | [x] Yes | Static sample data |

## C3: Data Corruption Simulation

### Test Procedure
1. Open browser DevTools > Application > Local Storage
2. Find key `demo_v1_routes`
3. Corrupt it: change to `{"broken":` (invalid JSON)
4. Navigate to Admin Console
5. **Expected**: "Data Integrity Issues Detected" with "Corrupted data in routes"
6. Click "Repair Issues" or "Reset All Data"
7. **Expected**: Data is repaired/reset, integrity shows "OK"

### Orphaned Data Test
1. Open DevTools > Application > Local Storage
2. Add key: `demo_v1_plan_detail_99999` with value `{}`
3. Navigate to Admin Console
4. **Expected**: "Orphaned plan detail: demo_v1_plan_detail_99999"
5. Click "Repair Issues"
6. **Expected**: Orphaned key removed

## C4: Golden Scenario Runbook

### What This Tests
The complete end-to-end workflow that the CEO follows every test session:
- Plan generation
- Plan acceptance
- Outcome entry
- Learning loop visibility
- Snapshot flow

### Prerequisites
- Browser with local storage enabled
- Access to deployed app (Vercel) or local dev server

---

## Golden Scenario Steps

### Step 1: Admin Setup
1. Navigate to `/admin`
2. Click **"Enable Full Access + Seed Everything"** (yellow button)
3. Wait for page reload
4. **Verify**:
   - Status shows "Demo Mode"
   - "Admin Override" badge is visible
   - Data Inventory shows: Organizations=1, Trucks=1, Routes=20

### Step 2: Generate Plans
1. Navigate to `/plans` (Preflight)
2. In the Planning Parameters panel:
   - Start Location: Chicago, IL (default)
   - Horizon: 7 days (default)
3. Click **"Generate Plans"**
4. **Verify**:
   - Plans appear in the plan list
   - Click a plan card to see details in the inspect panel
   - "Economics" tab shows per-load breakdown
   - "Copilot" tab shows plan status (OK/degraded/unknown)

### Step 3: Accept Plan
1. In the inspect panel, click the **"Track"** tab
2. Click **"Accept Plan"** (green button)
3. **Verify**:
   - "Accepted" badge appears
   - "Pending" status badge appears
   - "View History →" link is visible
   - Yellow "Enter Actuals" prompt appears

### Step 4: Enter Actuals & Complete Outcome
1. Click **"Enter Actuals"** button
2. Fill in the form:
   - Revenue: `2500`
   - Fuel Cost: `450`
   - Miles Loaded: `400`
   - Drive Time: `480`
3. Click **"Mark Complete"**
4. **Verify**:
   - Status changes to "Complete"
   - Variance table shows Predicted vs Actual with delta %
   - Learning Loop section appears with accuracy score

### Step 5: Verify History + Learning Loop
1. Navigate to `/plans/history`
2. **Verify**:
   - Recent plan shows in history list
   - Outcome summary shows completed status
   - Variance percentages are displayed
3. Click on the plan entry to expand
4. **Verify**: Full plan details are visible

### Step 6: Snapshot Flow
1. Navigate to `/snapshot`
2. Select a recent plan generation from the list
3. Select a plan from that generation
4. Click **"Generate Snapshot"**
5. **Verify**: Redirects to `/recommendations`
6. **Verify**: Recommendations are grouped by category (Operational, Negotiation, Risk)
7. Click **"Forward Look →"**
8. **Verify**: `/forward-look` shows:
   - Profit Scenarios (Best/Base/Worst)
   - Lane Repeat Insights
   - Plan Context summary

---

## Pass Criteria

All of the following must be true:
- [ ] Hard refresh works on all routes
- [ ] Deterministic functions produce same outputs for same inputs
- [ ] Data corruption is detected and can be repaired
- [ ] Golden scenario completes without errors
- [ ] No console errors during golden scenario
- [ ] Demo mode works fully offline (no network requests fail fatally)

---

## Known Limitations (Not Blocking)

1. **Live API**: Most endpoints return mock data in demo mode
2. **Copilot evaluation history**: Simulated in demo mode
3. **Risk outcome report**: Uses demo correlations
4. **Calibration report**: Uses sample demo metrics

These are expected behaviors in demo mode and do not constitute failures.
