import { Component } from 'react';
import { Inline, ReplyText } from './ResponseMicroUI.jsx';
import { ReplyControlsDisabled, ReplySummary } from './ReplyControls.jsx';
import { CarList } from './CarList.jsx';
import {
  VehicleDetails, VehicleGallery, ColorOptions, FinancingOffers,
  VehicleVisualization, CarComparison,
} from './VehicleExperience.jsx';

const vehicleComponents = {
  VehicleDetails, VehicleGallery, ColorOptions, FinancingOffers,
  VehicleVisualization, CarComparison,
};
const textRoles = new Set(['answer', 'body', 'notice', 'status']);

class BlockBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed
      ? this.props.fallback && <p className="response-body">{this.props.fallback}</p>
      : this.props.children;
  }
}

export function previousTurnsFor(turns, currentId, contextTurnId = null) {
  return turns.filter(turn =>
    turn.id < currentId && turn.blocks &&
    (contextTurnId === null || turn.id <= contextTurnId)
  ).slice(-20);
}

export function responseText(blocks) {
  const shownText = new Set(blocks.filter(block => block.type === 'text').map(block => block.text));
  return blocks.map(block => {
    if (block.type === 'text' || block.type === 'disclosure') return block.text || '';
    if (block.type === 'context') return (block.items || []).join(' · ');
    return shownText.has(block.fallback_text) ? '' : block.fallback_text || '';
  }).filter(Boolean).join('\n');
}

export function ResponseBlocks({ blocks, compare = false, onAction, disabled = false }) {
  const shownText = new Set(blocks.filter(block => block.type === 'text').map(block => block.text));
  const catalogIndex = blocks.findIndex(block =>
    block.type === 'ui' && block.component === 'CarList' && Array.isArray(block.props?.cars));
  const catalogContext = blocks[catalogIndex - 1];
  const integratedContext = catalogContext?.type === 'context' && Array.isArray(catalogContext.items)
    ? catalogContext : null;
  const content = blocks.map((block, index) => {
    const key = block.id || index;
    const fallback = shownText.has(block.fallback_text) ? null : block.fallback_text;
    if (block.type === 'text') {
      const role = textRoles.has(block.role) ? block.role : 'body';
      if (Array.isArray(block.citations)) {
        return <p key={key} className="response-body">
          <Inline text={block.text} />
          {block.citations.map(({ url, label }) => <a key={url} href={url} target="_blank"
            rel="noopener noreferrer" className="web-citation"> {label}</a>)}
        </p>;
      }
      return <ReplyText key={key} text={block.text} role={role} />;
    }
    if (block.type === 'context' && Array.isArray(block.items)) {
      if (block === integratedContext) return null;
      return <ul key={key} className="response-context" aria-label="Response context">
        {block.items.map((item, itemIndex) => <li key={itemIndex}>{item}</li>)}
      </ul>;
    }
    if (block.type === 'actions' && Array.isArray(block.actions)) {
      const actions = integratedContext ? block.actions.filter(action => action.id !== 'clear-budget') : block.actions;
      if (!actions.length) return null;
      return <div key={key} className="response-actions" role="group" aria-label={block.label || 'Suggested next steps'}>
        {actions.slice(0, block.choice === true ? 8 : 2).map((action, actionIndex) => (
          <button key={action.id || actionIndex} type="button"
            disabled={disabled || !onAction}
            onClick={disabled ? undefined : () => onAction?.(action)}>
            {action.label}
          </button>
        ))}
      </div>;
    }
    if (block.type === 'disclosure') {
      return <details key={key} className="response-disclosure">
        <ReplySummary>{block.title}</ReplySummary>
        <p>{block.text}</p>
      </details>;
    }
    if (block.type === 'ui' && block.component === 'CarList' && Array.isArray(block.props?.cars)) {
      return <BlockBoundary key={key} fallback={fallback}>
        <fieldset className="reply-controls" disabled={disabled}>
          <CarList cars={block.props.cars} startComparison={compare || block.props.startComparison}
            contextItems={index === catalogIndex ? integratedContext?.items : undefined} />
        </fieldset>
      </BlockBoundary>;
    }
    const VehicleComponent = Object.hasOwn(vehicleComponents, block.component)
      ? vehicleComponents[block.component] : null;
    if (block.type === 'ui' && VehicleComponent && Array.isArray(block.props?.records)) {
      return <BlockBoundary key={key} fallback={fallback}>
        <fieldset className="reply-controls" disabled={disabled}>
          <VehicleComponent records={block.props.records} />
        </fieldset>
      </BlockBoundary>;
    }
    return fallback ? <p className="response-body" key={key}>{fallback}</p> : null;
  });
  return <ReplyControlsDisabled value={disabled}>{content}</ReplyControlsDisabled>;
}
