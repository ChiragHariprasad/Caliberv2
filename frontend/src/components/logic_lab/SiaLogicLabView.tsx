import React, { useMemo, useState } from 'react';
import type { Driver } from '../../types';
import type {
  ContractDefinition,
  DecisionInstance,
  IntegrityState,
  SIAAssessment,
} from '../../types/calibre';
import { StateBadge } from '../shared/StateBadge';
import { SuperpositionView } from './SuperpositionView';
import { EntanglementGraph } from './EntanglementGraph';
import { ContextualityDag } from './ContextualityDag';
import { StateAlgebraTree } from './StateAlgebraTree';

interface SiaLogicLabViewProps {
  decisions: DecisionInstance[];
  verdicts: SIAAssessment[];
  contracts: ContractDefinition[];
  drivers: Driver[];
  sessionId?: string;
  sessionName?: string;
  selectedDecisionId?: string | null;
  onSelectDecision?: (instanceId: string) => void;
  className?: string;
}

type WorkspaceTab = 'ENVELOPE' | 'PROVENANCE' | 'CONTEXTUALITY' | 'EVALUATOR';

export const SiaLogicLabView: React.FC<SiaLogicLabViewProps> = ({
  decisions,
  verdicts,
  contracts,
  drivers,
  sessionId = 'f1-2026-monaco-sim',
  sessionName = 'Monaco Grand Prix (Simulation)',
  selectedDecisionId,
  onSelectDecision,
  className = '',
}) => {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('ENVELOPE');
  const [internalDecisionId, setInternalDecisionId] = useState<string>('');

  // Derive list of selectable real decision instances
  const availableDecisionIds = useMemo(() => {
    const set = new Set<string>();
    for (const d of decisions) {
      if (d.instance_id) set.add(d.instance_id);
    }
    for (const v of verdicts) {
      if (v.decision_instance_id) set.add(v.decision_instance_id);
    }
    return Array.from(set);
  }, [decisions, verdicts]);

  const currentDecisionId =
    (selectedDecisionId && availableDecisionIds.includes(selectedDecisionId) ? selectedDecisionId : '') ||
    (internalDecisionId && availableDecisionIds.includes(internalDecisionId) ? internalDecisionId : '') ||
    availableDecisionIds[0] ||
    selectedDecisionId ||
    '';

  const handleDecisionChange = (newId: string) => {
    setInternalDecisionId(newId);
    onSelectDecision?.(newId);
  };

  // Find active verdict for selected decision
  const activeVerdict = useMemo(() => {
    return verdicts.find((v) => v.decision_instance_id === currentDecisionId) || null;
  }, [verdicts, currentDecisionId]);

  // Extract real decision metadata
  const currentContractId = activeVerdict?.contract?.id || (currentDecisionId.split('@')[0] || 'lap_time');
  const currentState: IntegrityState = activeVerdict?.integrity_state || 'UNKNOWN';
  const maturity = activeVerdict?.resolution_maturity || 'OPEN';
  const lowerBound: IntegrityState = (activeVerdict?.envelope?.lower as IntegrityState) || 'DEGRADED';
  const upperBound: IntegrityState = (activeVerdict?.envelope?.upper as IntegrityState) || 'HEALTHY';

  const realSlots = useMemo(() => {
    if (!activeVerdict?.roles) return undefined;
    const entries = Object.entries(activeVerdict.roles);
    if (entries.length === 0) return undefined;
    const limiting = new Set(activeVerdict.limiting_children || []);
    return entries.map(([roleId, raw]) => {
      const r = raw as any;
      const atom = Array.isArray(r?.atoms_detail) ? r.atoms_detail[0] : undefined;
      const fact = Array.isArray(r?.reference_facts_detail) ? r.reference_facts_detail[0] : undefined;
      const hasEv = Boolean(r?.has_evidence || atom || fact);
      const val =
        atom?.value !== undefined
          ? `${atom.value} ${atom.unit || ''}`.trim()
          : fact?.value !== undefined
          ? `${String(fact.value)} ${fact.unit || ''}`.trim()
          : undefined;
      const src =
        atom?.source_origins?.[0] ||
        fact?.source_origins?.[0] ||
        (r?.dependencies || []).find((d: string) => d.startsWith('S:'))?.slice(2) ||
        'Awaiting source';
      const ts = atom?.observed_at || fact?.valid_from || r?.latest_observed_at || 'Awaiting admission';
      return {
        roleId,
        kind: (r?.kind === 'reference' ? 'reference' : 'evidence') as 'evidence' | 'reference',
        status: (hasEv ? 'ADMITTED' : r?.closed ? 'MISSING' : 'PENDING') as 'ADMITTED' | 'PENDING' | 'MISSING' | 'REJECTED',
        value: val ?? (hasEv ? 'Admitted' : '—'),
        source: src,
        timestamp: String(ts),
        isLimiting: limiting.has(roleId) || !hasEv,
      };
    });
  }, [activeVerdict]);

  const realCorroborationDepth = activeVerdict?.corroboration_depth ?? 0;
  const realHasCommonCause = (activeVerdict?.resilience?.critical_origins?.length ?? 0) > 0;

  return (
    <div className={`logic-lab-workbench-root ${className}`}>
      {/* 1. Page Header */}
      <header className="logic-lab-header">
        <div className="logic-lab-header-left">
          <div className="logic-lab-eyebrow">
            <span className="eyebrow-accent-square" />
            <span>SIA CORE V3 FORMAL WORKBENCH</span>
          </div>
          <h1 className="logic-lab-main-heading">SIA Logic Lab</h1>
          <p className="logic-lab-subheading">
            Deterministic integrity evaluation, evidence dependencies and epistemic analysis.
          </p>
        </div>

        <div className="logic-lab-header-right">
          <div className="evaluator-engine-chip">
            <span className="pulse-green-dot" />
            <span className="engine-name">DETERMINISTIC EVALUATOR READY</span>
            <span className="engine-regime">Bitemporal K-Clock Active</span>
          </div>
        </div>
      </header>

      {/* 2. Global Decision Context Bar */}
      <section className="logic-lab-context-bar" aria-label="Selected decision context">
        <div className="context-item context-item--session">
          <span className="ctx-label">ACTIVE SESSION:</span>
          <strong className="ctx-val text-slate-200">{sessionName}</strong>
          <code className="ctx-sub-code">{sessionId}</code>
        </div>

        <div className="context-item context-item--decision">
          <span className="ctx-label">SELECTED DECISION INSTANCE:</span>
          <select
            id="lab-decision-select"
            name="lab_decision_select"
            className="ctx-decision-select"
            value={currentDecisionId}
            onChange={(e) => handleDecisionChange(e.target.value)}
            aria-label="Select decision instance to inspect"
          >
            {availableDecisionIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </div>

        <div className="context-item context-item--contract">
          <span className="ctx-label">CONTRACT:</span>
          <span className="ctx-contract-badge">{currentContractId} v1.0.0</span>
        </div>

        <div className="context-item context-item--verdict">
          <span className="ctx-label">EVALUATED STATE:</span>
          <div className="ctx-verdict-badge">
            <StateBadge state={currentState} size="sm" />
          </div>
        </div>

        <div className="context-item context-item--maturity">
          <span className="ctx-label">RESOLUTION MATURITY:</span>
          <span className="ctx-maturity-tag font-mono">{maturity}</span>
        </div>

        <div className="context-item context-item--evidence">
          <span className="ctx-label">EVIDENCE SLOTS:</span>
          <span className="ctx-slots-count">
            {activeVerdict?.roles ? Object.keys(activeVerdict.roles).length : 5} Tracked Roles
          </span>
        </div>
      </section>

      {/* 3. Dedicated Workspace Navigation Tabs */}
      <nav className="logic-lab-tabs-nav" aria-label="SIA Workspaces">
        <button
          type="button"
          className={`workspace-tab-btn ${activeTab === 'ENVELOPE' ? 'is-active-tab' : ''}`}
          onClick={() => setActiveTab('ENVELOPE')}
        >
          <span className="tab-step-num">1</span>
          <span className="tab-title">State Envelope &amp; Superposition</span>
        </button>

        <button
          type="button"
          className={`workspace-tab-btn ${activeTab === 'PROVENANCE' ? 'is-active-tab' : ''}`}
          onClick={() => setActiveTab('PROVENANCE')}
        >
          <span className="tab-step-num">2</span>
          <span className="tab-title">Provenance &amp; Entanglement Graph</span>
        </button>

        <button
          type="button"
          className={`workspace-tab-btn ${activeTab === 'CONTEXTUALITY' ? 'is-active-tab' : ''}`}
          onClick={() => setActiveTab('CONTEXTUALITY')}
        >
          <span className="tab-step-num">3</span>
          <span className="tab-title">Contextuality &amp; Scope Isolation</span>
        </button>

        <button
          type="button"
          className={`workspace-tab-btn ${activeTab === 'EVALUATOR' ? 'is-active-tab' : ''}`}
          onClick={() => setActiveTab('EVALUATOR')}
        >
          <span className="tab-step-num">4</span>
          <span className="tab-title">Deterministic SIA Evaluator</span>
        </button>
      </nav>

      {/* 4. Active Dedicated Full-Width Workspace Content */}
      <main className="logic-lab-workspace-content">
        {activeTab === 'ENVELOPE' && (
          <SuperpositionView
            decisionId={currentDecisionId || 'Awaiting active decision'}
            contractId={`${currentContractId} v${activeVerdict?.contract?.version || '1.0.0'}`}
            lowerBound={lowerBound}
            upperBound={upperBound}
            currentState={currentState}
            maturity={maturity}
            openSlots={realSlots}
            availableDecisions={availableDecisionIds}
            onSelectDecision={handleDecisionChange}
          />
        )}

        {activeTab === 'PROVENANCE' && (
          <EntanglementGraph
            decisionId={currentDecisionId || 'Awaiting active decision'}
            contractId={currentContractId}
            corroborationDepth={realCorroborationDepth}
            hasCommonCause={realHasCommonCause}
            verdict={activeVerdict}
          />
        )}

        {activeTab === 'CONTEXTUALITY' && (
          <ContextualityDag
            decisionId={currentDecisionId}
            verdict={activeVerdict}
            allVerdicts={verdicts}
            contracts={contracts}
          />
        )}

        {activeTab === 'EVALUATOR' && (
          <StateAlgebraTree
            decisionId={currentDecisionId || 'Awaiting active decision'}
            contractId={currentContractId}
            verdict={activeVerdict}
          />
        )}
      </main>
    </div>
  );
};
