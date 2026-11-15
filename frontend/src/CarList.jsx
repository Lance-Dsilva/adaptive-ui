import { ReplySummary } from './ReplyControls.jsx';
import { useEffect, useId, useRef, useState } from 'react';
import { ComparisonPhoto } from './VehicleExperience.jsx';
import { askAboutVehicle, askShoppingQuestion, askToCompare } from './vehiclePrompts.js';

const powertrains = { gasoline: 'Gasoline', mild_hybrid: 'Mild hybrid', plug_in_hybrid: 'Plug-in hybrid' };
const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const price = value => Number.isFinite(value) ? usd.format(value) : 'Price unavailable';
export const modelName = name => name.replace(/^Mazda\s+(?=Mazda)/i, '');

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

export function CarList({ cars, startComparison = false }) {
  const scrollHintId = useId();
  const [showFilters, setShowFilters] = useState(false);
  const [limit, setLimit] = useState('');
  const [comparing, setComparing] = useState(startComparison);
  const [selected, setSelected] = useState([]);
  const [trimIds, setTrimIds] = useState({});
  const scrollRegion = useRef(null);
  const compareButton = useRef(null);
  const [listOverflows, setListOverflows] = useState(false);
  const visible = cars;
  const comparison = selected.map(id => cars.find(car => car.id === id)).filter(Boolean);
  const complete = comparing && comparison.length === 2;
  useEffect(() => {
    if (complete) compareButton.current?.focus();
  }, [complete]);
  useEffect(() => {
    const region = scrollRegion.current;
    if (!region) return;
    const measure = () => setListOverflows(region.scrollHeight > region.clientHeight + 1);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(region);
    if (region.firstElementChild) observer.observe(region.firstElementChild);
    return () => observer.disconnect();
  }, [visible.length]);

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

  return <div className="discovery">
    <div className="catalog-toolbar">
      <span>{comparing ? 'Choose cars to compare' : `${visible.length} matching models`}</span>
      <button type="button" aria-pressed={comparing} onClick={() => {
        setComparing(!comparing);
      }}>{comparing ? 'Browse models' : 'Compare models'}</button>
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
            onClick={() => askToCompare(picks)}>Compare cars</button>
        : <p className="selection-note">{comparison.length ? 'Choose one more car.' : 'Choose two cars to compare.'}</p>}
    </section>}
      <div className="catalog-filters">
        <button type="button" aria-expanded={showFilters} onClick={() => setShowFilters(!showFilters)}>Price filter</button>
        <button type="button" onClick={() => askShoppingQuestion('Which of these are hybrids?')}>Hybrids</button>
      </div>
      {showFilters && <label className="price-filter">Maximum starting MSRP
        <input type="number" min="0" inputMode="numeric" value={limit}
          onChange={event => setLimit(event.target.value)} placeholder="Any price" />
        <button type="button" disabled={limit === '' || !Number.isFinite(Number(limit)) || Number(limit) < 0}
          onClick={() => askShoppingQuestion(`Show me the same vehicles under $${limit}.`)}>Apply price filter</button>
      </label>}
      <div className="active-filters">
        <button type="button" onClick={() => askShoppingQuestion('Show me all 2027 Mazda models and clear filters.')}>Clear filters</button>
      </div>
      <div ref={scrollRegion} className="catalog-scroll-region" role="region" aria-label="Scrollable Mazda model list" aria-describedby={scrollHintId} tabIndex="0">
      <ul className="vehicle-cards compact-model-list" aria-label="Matching Mazda models">
        {visible.map(car => {
          const configs = configurations(car);
          const seats = seatingSummary(configs);
          const bodies = [...new Set(configs.map(item => item.body_style).filter(Boolean))];
          const drives = [...new Set(configs.map(item => item.drivetrain).filter(Boolean))];
          return <li key={car.id} className="vehicle-card">
            <div className="vehicle-row-main">
            <ComparisonPhoto record={{ model: { name: modelName(car.name), model_year: car.year }, image_url: car.image_url, photos: car.photos, image_caption: car.image_caption, image_is_reference: car.image_is_reference }} />
            <div className="vehicle-card-content">
              <div className="vehicle-card-title"><span>{car.year}</span><h3>{modelName(car.name)}</h3></div>
              <p className="vehicle-starting-price"><strong>{price(car.msrp)}</strong><span>Starting MSRP</span></p>
            </div>
            <button className="vehicle-row-trigger" type="button"
              aria-pressed={comparing ? selected.includes(car.id) : undefined}
              disabled={complete && !selected.includes(car.id)}
              aria-label={comparing ? `${selected.includes(car.id) ? 'Remove' : 'Select'} ${modelName(car.name)} ${selected.includes(car.id) ? 'from' : 'for'} comparison` : `Explore model ${modelName(car.name)}`}
              onClick={() => comparing ? toggleCar(car.id) : askAboutVehicle('details', car)}>
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
                  <button type="button" onClick={() => askAboutVehicle('details', car)}>Explore model</button>
                  <button type="button" onClick={() => askAboutVehicle('photos', car)}>View photos</button>
                </div>
                <ul>{configs.map(trim => <li key={trim.trim_id}>
                  <span>{trim.name}<small>{[trim.body_style, trim.drivetrain, trim.seating_capacity && `${trim.seating_capacity} seats`].filter(Boolean).join(' · ')}</small></span>
                  <strong>{price(trim.msrp_usd === '' || trim.msrp_usd == null ? NaN : Number(trim.msrp_usd))}</strong>
                </li>)}</ul>
                <div className="filter-actions">
                  <button type="button" onClick={() => askAboutVehicle('colors', car)}>Colors & materials</button>
                  <button type="button" onClick={() => askAboutVehicle('financing', car)}>Financing</button>
                </div>
              </details>
          </li>;
        })}
      </ul>
      </div>
      {visible.length === 0 && <p className="catalog-empty" role="status">No models match these filters. Clear filters to see the catalog.</p>}
  </div>;
}
