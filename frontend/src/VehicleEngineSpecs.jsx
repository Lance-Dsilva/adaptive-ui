import { ReplySummary } from './ReplyControls.jsx';
import './VehicleEngineSpecs.css';

const ratingGroups = [
  { label: 'Power', field: 'ENGINE HORSEPOWER' },
  { label: 'Torque', field: 'ENGINE TORQUE' },
];
const fuelGrades = ['Regular', 'Premium'];

function matchingRatings(specifications, field) {
  const ratings = fuelGrades.map(grade => specifications.filter(item =>
    item.field.toUpperCase() === `${field} WITH ${grade.toUpperCase()} UNLEADED FUEL` &&
    item.value?.trim()
  ));
  if (ratings.some(matches => matches.length !== 1)) return [];
  const [regular, premium] = ratings.map(([item]) => item);
  // Only pair measurements that describe the same configuration and applicability.
  if (['model_id', 'trim_id', 'product_trim_code', 'applicability']
    .some(key => regular[key] !== premium[key])) return [];
  return ratings.map(([item], index) => ({ grade: fuelGrades[index], item }));
}

function FuelRating({ grade, item, noteFor }) {
  const measuredAt = /^(.+?)\s*@\s*([\d,]+(?:\s*-\s*[\d,]+)?\s+rpm)$/i.exec(item.value);
  const note = noteFor(item.applicability);
  return <div className="engine-fuel-rating">
    <span className="engine-fuel-grade">{grade} unleaded</span>
    {measuredAt
      ? <><strong>{measuredAt[1]}</strong><span>{measuredAt[2].replace(/\s*-\s*/, '–')}</span></>
      : <strong>{item.value}</strong>}
    {note && <small>{note}</small>}
  </div>;
}

export function VehicleEngineSpecs({ specifications, renderFact, noteFor = value => value }) {
  const engine = specifications.find(item => item.field.toUpperCase() === 'ENGINE TYPE');
  const grouped = ratingGroups.map(group => ({
    ...group, ratings: matchingRatings(specifications, group.field),
  })).filter(group => group.ratings.length);
  const leadingFacts = ['REDLINE', 'VALVETRAIN']
    .map(field => specifications.find(item => item.field.toUpperCase() === field))
    .filter(Boolean);
  const displayed = new Set([
    engine, ...leadingFacts, ...grouped.flatMap(group => group.ratings.map(({ item }) => item)),
  ]);
  const remaining = specifications.filter(item => !displayed.has(item));
  const showMore = engine && grouped.length === ratingGroups.length &&
    leadingFacts.length === 2 && remaining.length > 0;

  return <>
    <dl className="vehicle-specifications engine-specifications">
      {engine && renderFact(engine, 'engine', { label: 'Engine' })}
      {grouped.map(({ label, ratings }) => <div key={label}>
        <dt>{label}</dt>
        <dd className="engine-fuel-ratings">
          {ratings.map(rating => <FuelRating key={rating.grade} {...rating}
            noteFor={noteFor} />)}
        </dd>
      </div>)}
      {leadingFacts.map((item, index) => renderFact(item, `leading-${index}`))}
      {!showMore && remaining.map((item, index) => renderFact(item, index))}
    </dl>
    {showMore && <details className="engine-spec-more">
      <ReplySummary>More engine &amp; mechanical specs</ReplySummary>
      <dl className="vehicle-specifications">
        {remaining.map((item, index) => renderFact(item, index))}
      </dl>
    </details>}
  </>;
}
