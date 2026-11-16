import { ReplySummary } from './ReplyControls.jsx';
import { useEffect, useId, useRef, useState } from 'react';
import { ComparisonPhoto } from './VehicleExperience.jsx';
import { browseRequest, compareVehicles, openVehicle, runCatalogAction } from './catalogActions.js';

const powertrains = { gasoline: 'Gasoline', mild_hybrid: 'Mild hybrid', plug_in_hybrid: 'Plug-in hybrid' };
const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const price = value => Number.isFinite(value) ? usd.format(value) : 'Price unavailable';
export const modelName = name => name.replace(/^Mazda\s+(?=Mazda)/i, '');
const bodyLabels = new Map([['SUVs', 'SUVs'], ['Sedans', 'sedans'], ['Hatchbacks', 'hatchbacks']]);

function ToolbarIcon({ name }) {
  const paths = {
    price: 'M3 4h7l6 6-6 6-7-7V4Zm4 3h.01',
    hybrid: 'm10 2-6 8h5l-1 6 6-8H9l1-6Z',
    compare: 'M3 4h12v10H3zM9 4v10',
  };
  return <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}

export function seatingSummary(configs) {
  const seats = [...new Set(configs.flatMap(item => String(item.seating_capacity || '').split('|'))
    .map(value => value.trim()).filter(value => /^\d+$/.test(value)).map(Number))].sort((a, b) => a - b);
  if (!seats.length) return '';
  if (seats.length > 2 && seats.every((value, index) => !index || value === seats[index - 1] + 1)) return `${seats[0]}–${seats.at(-1)} seats`;
  return `${seats.length > 1 ? seats.slice(0, -1).join(', ') + ' or ' : ''}${seats.at(-1)} seats`;
}

function configurations(car) {
  return car.configurations?.length ? car.configurations : car.trims.map(trim => ({
    ...trim, trim_id: trim.id, msrp_usd: trim.msrp, specifications: [],
  }));
}

export function CarList({ cars, startComparison = false, contextItems = [], catalogFilters = {}, comparisonFocus = "" }) {
  const priceFormId = useId();
  const [showFilters, setShowFilters] = useState(false);
  const [limit, setLimit] = useState('');
  const [comparing, setComparing] = useState(startComparison);
  const [selected, setSelected] = useState([]);
  const [trimIds, setTrimIds] = useState({});
  const compareButton = useRef(null);
  const year = contextItems.find(item => /^20\d{2}$/.test(item)) || cars[0]?.year;
  const body = contextItems.find(item => bodyLabels.has(item));
  const filters = contextItems.filter(item => item !== String(year) && item !== body);
  const hasPrice = filters.some(item => /^Up to \$/.test(item));
  const hasHybrid = filters.some(item => /\bhybrids?\b/i.test(item));
  const catalogName = [year, 'Mazda', bodyLabels.get(body) || 'models'].filter(Boolean).join(' ');
  const browse = (label, nextFilters) => runCatalogAction(label,
    browseRequest(nextFilters, { compare: comparing, focus: comparisonFocus || undefined }));
  const comparison = selected.map(id => cars.find(car => car.id === id)).filter(Boolean);
  const complete = comparing && comparison.length === 2;
  useEffect(() => {
    if (complete) compareButton.current?.focus();
  }, [complete]);

  function toggleCar(id) {
    setSelected(current => current.includes(id)
      ? current.filter(value => value !== id)
      : current.length < 2 ? [...current, id] : current);
  }
  const picks = comparison.map(car => {
    const choices = configurations(car);
    const lowest = choices.reduce((best, item) =>
      item.msrp_usd && (!best?.msrp_usd || Number(item.msrp_usd) < Number(best.msrp_usd))
        ? item : best, choices[0]);
    return { car, choices, trim: choices.find(item => item.trim_id === trimIds[car.id]) || lowest };
  });

  return <section className="discovery" aria-label={catalogName}>
    <div className="catalog-toolbar">
      <div className="catalog-heading">
        <h3>{catalogName}</h3>
        <span>{cars.length} {cars.length === 1 ? 'model' : 'models'}</span>
      </div>
      <div className="catalog-filters" role="group" aria-label="Filter and compare models">
        <button type="button" aria-expanded={showFilters} aria-controls={showFilters ? priceFormId : undefined}
          data-applied={hasPrice || undefined} onClick={() => setShowFilters(!showFilters)}>
          <ToolbarIcon name="price" />Price
        </button>
        <button type="button" data-applied={hasHybrid || undefined}
          onClick={() => browse('Hybrids', { ...catalogFilters, powertrain: 'hybrid', model_powertrains: {} })}>
          <ToolbarIcon name="hybrid" />Hybrids
        </button>
        <button type="button" className="catalog-compare" aria-pressed={comparing}
          onClick={() => setComparing(!comparing)}>
          <ToolbarIcon name="compare" />{comparing ? 'Done' : 'Compare'}
        </button>
      </div>
      {showFilters && <form id={priceFormId} className="price-filter" onSubmit={event => {
        event.preventDefault();
        if (limit !== '' && Number.isFinite(Number(limit)) && Number(limit) >= 0) {
          browse(`Up to ${usd.format(Number(limit))}`, { ...catalogFilters, budget: Number(limit) });
        }
      }}>
        <label>Maximum starting MSRP
          <input type="number" min="0" step="0.01" inputMode="decimal" value={limit}
            onChange={event => setLimit(event.target.value)} placeholder="Any price" required />
        </label>
        <button type="submit" disabled={limit === '' || !Number.isFinite(Number(limit)) || Number(limit) < 0}>
          Apply
        </button>
      </form>}
      {filters.length > 0 && <div className="active-filters" aria-label="Applied filters">
        <ul>{filters.map((item, index) => <li key={index}>{item}</li>)}</ul>
        <button type="button" onClick={() => browse('Clear filters', { year: Number(year), body_style: catalogFilters.body_style })}>
          Clear filters
        </button>
      </div>}
    </div>
    {comparing && <section className="compare-picker" aria-label="Comparison selection">
      <p role="status">{comparison.length} of 2 selected</p>
      {picks.map(({ car, choices, trim }) => <div className="compare-pick" key={car.id}>
        <div className="compare-pick-heading">
          <strong>{car.year} {modelName(car.name)}</strong>
          <button type="button" aria-label={`Remove ${modelName(car.name)} from comparison`}
            onClick={() => toggleCar(car.id)}>Remove</button>
        </div>
        {trim && <p className="compare-pick-caption">{[trim.name, trim.body_style === 'suv' ? 'SUV' : trim.body_style,
          trim.drivetrain].filter(Boolean).join(' · ')}
          {trim.msrp_usd && <span>{price(Number(trim.msrp_usd))} base MSRP</span>}
        </p>}
        {trim && <label>Configuration
          <select aria-label={`${modelName(car.name)} configuration`} value={trim.trim_id}
            onChange={event => {
              const id = event.target.value;
              setTrimIds(current => ({ ...current, [car.id]: id }));
            }}>
            {choices.map(item => <option key={item.trim_id} value={item.trim_id}>
              {[item.name, item.body_style, item.drivetrain,
                item.seating_capacity && `${item.seating_capacity.replaceAll('|', ' or ')} seats`]
                .filter(Boolean).join(' · ')}
            </option>)}
          </select>
        </label>}
      </div>)}
      {complete
        ? <button ref={compareButton} className="primary-action compare-submit" type="button"
            disabled={!picks.every(({ trim }) => trim?.trim_id)}
            onClick={() => compareVehicles(picks, comparisonFocus)}>Compare cars</button>
        : <p className="selection-note">{comparison.length ? 'Choose one more car.' : 'Choose two cars to compare.'}</p>}
    </section>}
      <div className="catalog-scroll-region" role="region" aria-label="Scrollable Mazda model list" tabIndex="0">
      <ul className="vehicle-cards compact-model-list" aria-label="Matching Mazda models">
        {cars.map(car => {
          const configs = configurations(car);
          const seats = seatingSummary(configs);
          const bodies = [...new Set(configs.map(item => item.body_style).filter(Boolean))];
          const drives = [...new Set(configs.map(item => item.drivetrain).filter(Boolean))];
          const photoYear = car.image_is_reference && /^\d{4}/.exec(car.image_caption || '')?.[0];
          return <li key={car.id} className="vehicle-card">
            <div className="vehicle-row-main">
            <ComparisonPhoto hideCaption record={{ model: { name: modelName(car.name), model_year: car.year }, image_url: car.image_url, photos: car.photos, image_caption: car.image_caption, image_is_reference: car.image_is_reference }} />
            <div className="vehicle-card-content">
              <div className="vehicle-card-title"><h3>{modelName(car.name)}</h3></div>
              <p className="vehicle-starting-price">
                {Number.isFinite(car.msrp) && <span aria-label="Starting MSRP">From </span>}
                <strong>{price(car.msrp)}</strong>
              </p>
              {photoYear && <small className="catalog-photo-year">{photoYear} photo</small>}
            </div>
            <button className="vehicle-row-trigger" type="button"
              aria-pressed={comparing ? selected.includes(car.id) : undefined}
              disabled={complete && !selected.includes(car.id)}
              aria-label={comparing ? `${selected.includes(car.id) ? 'Remove' : 'Select'} ${modelName(car.name)} ${selected.includes(car.id) ? 'from' : 'for'} comparison` : `Explore model ${modelName(car.name)}`}
              onClick={() => comparing ? toggleCar(car.id) : openVehicle('details', car)}>
              <span aria-hidden="true">{comparing ? selected.includes(car.id) ? '✓' : '+' : '›'}</span>
            </button>
            </div>
              <details className="model-configurations"><ReplySummary>Model information <span>{configs.length} configurations</span></ReplySummary>
                <ul className="vehicle-highlights" aria-label="Model highlights">
                  <li>{powertrains[car.powertrain] || 'Powertrain unavailable'}</li>
                  {bodies.length > 0 && <li>{bodies.join(' / ')}</li>}
                  {seats && <li>{seats}</li>}
                  {drives.length > 0 && <li>{drives.join(' / ')}</li>}
                </ul>
                <div className="vehicle-card-actions">
                  <button type="button" onClick={() => openVehicle('details', car)}>Explore model</button>
                  <button type="button" onClick={() => openVehicle('photos', car)}>View photos</button>
                </div>
                <ul>{configs.map(trim => <li key={trim.trim_id}>
                  <span>{trim.name}<small>{[trim.body_style, trim.drivetrain, trim.seating_capacity && `${trim.seating_capacity} seats`].filter(Boolean).join(' · ')}</small></span>
                  <strong>{price(trim.msrp_usd === '' || trim.msrp_usd == null ? NaN : Number(trim.msrp_usd))}</strong>
                </li>)}</ul>
                <div className="filter-actions">
                  <button type="button" onClick={() => openVehicle('colors', car)}>Colors & materials</button>
                  <button type="button" onClick={() => openVehicle('financing', car)}>Financing</button>
                </div>
              </details>
          </li>;
        })}
      </ul>
      </div>
      {cars.length === 0 && <p className="catalog-empty" role="status">No models match these filters.</p>}
  </section>;
}
