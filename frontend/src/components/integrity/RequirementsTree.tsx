import React from 'react';
import type { IntegrityState, RoleEvaluation } from '../../types/calibre';
import { StateBadge } from '../shared/StateBadge';

interface RequirementsTreeProps {
  formula: string; // e.g. "AND(timing_speed, vehicle_speed, configured_distance)"
  rootState: IntegrityState;
  roles: Record<string, RoleEvaluation>;
  limitingChildren?: string[];
  onSelectRole?: (roleId: string) => void;
  selectedRoleId?: string | null;
  className?: string;
}

export const RequirementsTree: React.FC<RequirementsTreeProps> = ({
  formula,
  rootState,
  roles,
  limitingChildren = [],
  onSelectRole,
  selectedRoleId,
  className = '',
}) => {
  const roleEntries = Object.entries(roles);

  // Extract operator from formula (e.g. AND, OR, k-of-n)
  const isOR = formula.toUpperCase().startsWith('OR');
  const isAND = formula.toUpperCase().startsWith('AND') || !isOR;
  const operatorLabel = isOR ? 'OR (Join — Highest Grade)' : 'AND (Meet — Weakest Link Wins)';

  return (
    <div className={`requirements-tree-card ${className}`}>
      <div className="requirements-tree__header">
        <span className="req-title">Deterministic Requirements Logic Tree</span>
        <span className="req-formula">
          <code>{formula || 'AND(roles...)'}</code>
        </span>
      </div>

      <div className="tree-container">
        {/* Root Evaluation Node */}
        <div className="tree-node tree-node--root">
          <div className="node-content root-content">
            <span className="node-operator">{operatorLabel}</span>
            <div className="node-verdict-row">
              <span className="node-name">Root Evaluator Verdict</span>
              <StateBadge state={rootState} size="sm" />
            </div>
          </div>
        </div>

        {/* Tree Branch Connectors */}
        <div className="tree-branches-connector">
          <div className="vertical-stem" />
          <div className="horizontal-bar" />
        </div>

        {/* Children Roles Grid */}
        <div className="tree-children-grid">
          {roleEntries.length === 0 ? (
            <div className="tree-empty-state">
              <span>No evidence roles admitted yet.</span>
            </div>
          ) : (
            roleEntries.map(([roleId, roleEval]) => {
              const isLimiting = limitingChildren.includes(roleId);
              const isSelected = selectedRoleId === roleId;
              const childState = roleEval.state || roleEval.atom?.quality_grade || 'UNKNOWN';
              const observedVal = roleEval.atom ? `${roleEval.atom.value} ${roleEval.atom.unit}` : 'Awaiting arrival';
              const sourceOrigin = roleEval.atom?.source_origins?.join(', ') || 'Pending';

              return (
                <div
                  key={roleId}
                  className={`child-role-card ${isLimiting ? 'is-weakest-link' : ''} ${
                    isSelected ? 'is-selected' : ''
                  }`}
                  onClick={() => onSelectRole?.(roleId)}
                  role="button"
                  tabIndex={0}
                  title={isLimiting ? 'Weakest-link child that determined the root verdict' : undefined}
                >
                  <div className="child-role__header">
                    <span className="child-role-id">{roleId}</span>
                    <StateBadge state={childState} size="sm" />
                  </div>

                  <div className="child-role__details">
                    <div className="detail-row">
                      <span className="d-label">Observed:</span>
                      <strong className="d-val">{observedVal}</strong>
                    </div>
                    <div className="detail-row">
                      <span className="d-label">Source:</span>
                      <span className="d-val">{sourceOrigin}</span>
                    </div>
                    {roleEval.corroboration_depth !== undefined && (
                      <div className="detail-row">
                        <span className="d-label">Depth:</span>
                        <span className="d-val">{roleEval.corroboration_depth} disjoint</span>
                      </div>
                    )}
                  </div>

                  {isLimiting && (
                    <div className="weakest-link-banner">
                      <span className="weakest-tag">LIMITING PATH:</span>
                      <span>Decisive Weakest-Link Node</span>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

