import { ReplySummary } from './ReplyControls.jsx';
import { useState } from 'react';
import { askAboutVehicle, askShoppingQuestion, askToCompare, isFullFeatureComparison } from './vehiclePrompts.js';
import VehicleVisualizer, { verifiedSequences } from './VehicleVisualization.jsx';
import { VehicleEngineSpecs } from './VehicleEngineSpecs.jsx';
import { isHttpsUrl as https } from './isHttpsUrl.js';
import './VehicleDetails.css';
export { verifiedSequences } from './VehicleVisualization.jsx';

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const wholeDollarPrice = new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD', maximumFractionDigits: 0,
});
function number(value) {
  if (value === '' || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
function price(value) {
  const parsed = number(value);
  return parsed === null ? 'Unavailable' : money.format(parsed);
}
export function displayCaption(value) {
  const caption = typeof value === 'string' ? value.trim() : '';
  const isMetadata = /(?:https?:\/\/|www\.|file:\/\/|^[a-z]:[\\/]|^\.{0,2}\/)/i.test(caption) ||
    /\.(?:png|jpe?g|webp|gif|avif|svg|tiff?|bmp)(?:[?#\s]|$)/i.test(caption) ||
    /^(?:[^\s/\\]+[/\\])+[^\s]*$/.test(caption);
  return caption && !isMetadata ? caption : 'Vehicle reference image';
}

function Photo({ asset, modelYear, modelName }) {
  const [failed, setFailed] = useState(false);
  if (!asset || !https(asset.url) || failed) return <p className="photo-empty" role="status">Photo unavailable for this selection.</p>;
  const caption = comparisonCaption({ model: { model_year: modelYear, name: modelName } }, asset);
  return <figure className="vehicle-photo">
    <img src={asset.url} alt={caption || modelName || 'Vehicle photo'} loading="lazy"
      referrerPolicy="no-referrer" onError={() => setFailed(true)} />
    {caption && <figcaption>{caption}</figcaption>}
  </figure>;
}
export function vehiclePhotos(record) {
  const trimCodes = new Set((record.trims || []).map(trim => trim.product_trim_code).filter(Boolean));
  const trimIds = new Set((record.trims || []).map(trim => trim.trim_id));
  const unique = new Set();
  return (record.assets || []).filter(asset => {
    if (asset.asset_kind !== 'image' || !https(asset.url) ||
        !((asset.model_id === record.model_id && asset.source_model_year === record.model_year) ||
          (asset.applicability === 'model_reference' && asset.reference_model_id === record.model_id)) ||
        (asset.reference_trim_id && !trimIds.has(asset.reference_trim_id)) ||
        asset.source_field === 'swatchImageUrl' ||
        (asset.applicability !== 'model_reference' && asset.product_trim_code && !trimCodes.has(asset.product_trim_code)) ||
        unique.has(asset.url)) return false;
    unique.add(asset.url);
    return true;
  });
}

function selectTrim(record, trim) {
  const applicable = row => {
    if (row.applicability === 'model_reference') {
      return row.reference_model_id === record.model_id &&
        (!row.reference_trim_id || row.reference_trim_id === trim.trim_id);
    }
    return (!row.trim_id || row.trim_id === trim.trim_id) &&
      (!row.product_trim_code || row.product_trim_code === trim.product_trim_code);
  };
  return { ...record, trims: [trim],
    assets: (record.assets || []).filter(applicable),
    colors: (record.colors || []).filter(applicable),
    specifications: (record.specifications || []).filter(applicable),
    visualizations: (record.visualizations || []).filter(applicable) };
}

function Gallery({ record }) {
  const [trimId, setTrimId] = useState(record.trims?.[0]?.trim_id || '');
  const trim = record.trims?.find(item => item.trim_id === trimId);
  const assets = vehiclePhotos(trim ? selectTrim(record, trim) : record);
  const [selected, setSelected] = useState(0);
  const index = Math.min(selected, Math.max(0, assets.length - 1));
  return <section className="experience-card">
    <h3>{record.model_year} {record.name} photos</h3>
    {record.trims?.length > 1 && <label>Photo configuration<select value={trimId}
      onChange={event => { setTrimId(event.target.value); setSelected(0); }}>
      {record.trims.map(item => <option key={item.trim_id} value={item.trim_id}>
        {item.name} · {item.drivetrain} · {item.seating_capacity} seats
      </option>)}
    </select></label>}
    {trim && <p className="experience-note">{trim.name} · {trim.drivetrain}</p>}
    <Photo modelYear={record.model_year} modelName={record.name} key={assets[index]?.url || 'empty'} asset={assets[index]} />
    {assets.length > 1 && <div className="gallery-controls">
      <button type="button" aria-label="Previous photo" disabled={index === 0}
        onClick={() => setSelected(index - 1)}>Previous</button>
      <span role="status" aria-live="polite">Photo {index + 1} of {assets.length}</span>
      <button type="button" aria-label="Next photo" disabled={index === assets.length - 1}
        onClick={() => setSelected(index + 1)}>Next</button>
    </div>}
  </section>;
}
export function VehicleGallery({ records = [] }) {
  return records.length ? records.map(record => <Gallery key={record.model_id} record={record} />)
    : <p>No vehicle media is available.</p>;
}

function PaintSwatch({ color }) {
  const hex = [color.swatch_hex, color.hex_value, color.major_color_hex]
    .map(value => (value || '').trim().replace(/^#/, ''))
    .find(value => /^[a-f0-9]{6}$/i.test(value));
  if (!hex) return <span className="color-swatch color-swatch-unavailable"
    aria-label="Swatch unavailable" role="img">—</span>;
  return <span className="color-swatch" aria-hidden="true" style={{ backgroundColor: `#${hex}` }} />;
}

export function colorPreviewPhotos(record, color) {
  if (!color?.color_code) return [];
  const trim = record.trims?.find(item => item.trim_id === color.trim_id);
  const trimCode = color.product_trim_code || trim?.product_trim_code;
  const scopedRecord = trim ? selectTrim(record, trim) : record;
  const fields = color.location === 'interior'
    ? ['bpTopImage', 'bpBottomLeftImage', 'bpBottomRightImage', 'imageUrl']
    : ['bpTopLeftImage', 'bpTopRightImage', 'bpBottomImage', 'imageUrl'];
  return vehiclePhotos(scopedRecord).filter(asset =>
    asset.color_code === color.color_code &&
    (!trimCode || asset.product_trim_code === trimCode) &&
    fields.includes(asset.source_field)
  ).sort((a, b) => fields.indexOf(a.source_field) - fields.indexOf(b.source_field));
}

function ColorPreview({ record, color }) {
  const [index, setIndex] = useState(0);
  const photos = colorPreviewPhotos(record, color);
  const exterior = color.location === 'exterior';
  const frame = exterior && color.color_code
    ? verifiedSequences(record).find(item =>
        item.color_code === color.color_code && !/interior/i.test(item.kind) &&
        (!color.product_trim_code || color.product_trim_code === item.product_trim_code))
    : null;
  const asset = photos[index];
  const url = asset?.url || (index === photos.length ? frame?.frames[0] : null);
  const label = exterior ? 'Exterior' : 'Interior';
  const imageYear = asset?.source_model_year;
  return <section className="color-preview" aria-label={`${color.name} preview`}>
    <h4>{color.name} · {label}
      {imageYear && imageYear !== record.model_year && <small className="color-preview-year"> · {imageYear} photo</small>}
    </h4>
    {url ? <figure className="vehicle-photo">
      <img key={url} src={url} alt={`${record.name} · ${color.name} ${label.toLowerCase()} reference`}
        referrerPolicy="no-referrer" onError={() => setIndex(current => current + 1)} />
    </figure> : <p className="photo-empty" role="status">
      {index > 0 ? 'The matching preview could not load.' : `No matching ${label.toLowerCase()} photo is available for this selection.`}
    </p>}
  </section>;
}

function Colors({ record }) {
  const colors = record.colors || [];
  const selectedColorId = record.selected_color_id;
  const color = colors.find(item => item.color_id === selectedColorId);
  return <section className="experience-card">
    <h3>{record.name} colors and materials</h3>
    {color && <ColorPreview key={color.color_id} record={record} color={color} />}
    {!colors.length && <p>Verified color choices are unavailable for this configuration.</p>}
    <div className="color-options">
      {colors.map(item => {
        const trim = record.trims?.find(trim => trim.trim_id === item.trim_id ||
          (item.product_trim_code && trim.product_trim_code === item.product_trim_code));
        return <button key={item.color_id} type="button" aria-pressed={selectedColorId === item.color_id}
          onClick={() => askAboutVehicle('colors', record, trim ||
            (record.trims?.length === 1 ? record.trims[0] : undefined), item)}>
          <PaintSwatch color={item} />
          <span>{item.name}<small>{item.location} · {trim?.name || 'Model-level availability'}</small></span>
          <span>{number(item.extra_cost_usd) === null ? 'Price unverified' : price(item.extra_cost_usd)}
            {selectedColorId === item.color_id && <small>Selected</small>}
          </span>
        </button>;
      })}
    </div>
    <p className="experience-note">Screen colors are approximate. Confirm trim, seating, and exterior/interior combinations with the dealer.</p>
  </section>;
}
export function ColorOptions({ records = [] }) {
  return records.length ? records.map(record => <Colors key={record.model_id} record={record} />)
    : <p>Verified color options are unavailable.</p>;
}

function Visualization({ record }) {
  return <VehicleVisualizer record={record} fallback={<Gallery record={record} />} />;
}
export function VehicleVisualization({ records = [] }) {
  return records.length ? records.map(record => <Visualization key={record.model_id} record={record} />)
    : <p>Verified visualization data is unavailable.</p>;
}

const powertrainLabels = {
  mild_hybrid: 'Mild hybrid',
  plug_in_hybrid: 'Plug-in hybrid',
  gasoline: 'Gasoline',
};

function specValue(item) {
  return item.value === 'N/A (source lists no Level 3 charging)' ? 'N/A (no Level 3 charging listed)' : item.value;
}

function renderSpecFact(item, index, { label = factLabel(item.field) } = {}) {
  return <div key={index}>
    <dt>{label}</dt>
    <dd>{specValue(item)}{specificationNote(item.applicability) && <small>{specificationNote(item.applicability)}</small>}
    </dd>
  </div>;
}

function VehicleSpecs({ groups }) {
  return <details className="vehicle-detail-expand">
    <ReplySummary>
      <strong>Features &amp; specs</strong>
      <small>{groups.map(([category]) => factLabel(category)).join(' · ')}</small>
    </ReplySummary>
    {groups.map(([category, facts]) => <details className="vehicle-spec-group" key={category}>
      <ReplySummary>{factLabel(category)}</ReplySummary>
      {category.toLowerCase() === 'engine & mechanical'
        ? <VehicleEngineSpecs specifications={facts} renderFact={renderSpecFact} noteFor={specificationNote} />
        : <dl className="vehicle-specifications">{facts.map((item, index) => renderSpecFact(item, index))}</dl>}
    </details>)}
  </details>;
}

function OverviewPhoto({ record, sequence, asset }) {
  const [failed, setFailed] = useState(false);
  if (!sequence || failed) return <Photo modelYear={record.model_year} modelName={record.name} asset={asset} />;
  const color = record.colors.find(item => item.color_code === sequence.color_code && item.location === 'exterior');
  const caption = color ? `${color.name} · Representative exterior` : 'Representative exterior';
  return <figure className="vehicle-photo vehicle-detail-preview">
    <img src={sequence.frames[0]} alt={`${record.name} · ${caption}`} loading="lazy" onError={() => setFailed(true)} />
    <figcaption>{caption}</figcaption>
  </figure>;
}

function Details({ record }) {
  const color = record.colors?.find(item => item.color_id === record.selected_color_id);
  const reference = color && record.trims?.length > 1 && !color.trim_id && !color.product_trim_code
    ? colorPreviewPhotos(record, color).find(asset => asset.reference_trim_id) : null;
  const trimId = record.selected_trim_id || color?.trim_id || reference?.reference_trim_id;
  const trim = record.trims?.find(item => item.trim_id === trimId) ||
    record.trims?.find(item => color?.product_trim_code && item.product_trim_code === color.product_trim_code) ||
    record.trims?.[0];
  if (!trim) return <p>Published configurations are unavailable for {record.name}.</p>;
  const selected = selectTrim(record, trim);
  const sequence = color ? null : verifiedSequences(selected)[0];
  const photos = color ? [] : vehiclePhotos(selected);
  const hero = photos.find(asset => asset.source_field === 'trim_image') || photos[0];
  const groups = new Map();
  for (const item of selected.specifications) {
    const category = specificationGroup(item);
    if (!groups.has(category)) groups.set(category, []);
    groups.get(category).push(item);
  }
  const regularPower = selected.specifications.find(item =>
    /^(ENGINE HORSEPOWER WITH REGULAR UNLEADED FUEL|HORSEPOWER WITH 87 OCTANE UNLEADED FUEL|horsepower_87_aki)$/i.test(item.field));
  const power = regularPower?.value.match(/^\s*(\d+(?:\.\d+)?)\s*(?:hp\b|$)/i)?.[1];
  const seats = trim.seating_capacity?.split('|').join(' or ');
  const automatic = /^(\d+)AT$/.exec(trim.transmission)?.[1];
  const facts = [
    [power && `${power} hp`, 'Regular fuel'],
    [seats && `${seats} seats`, trim.seating_rows ? `${trim.seating_rows} rows` : 'Seating'],
    [trim.drivetrain, automatic ? `${automatic}-speed auto` : 'Drivetrain'],
  ].filter(([value]) => value);
  const base = number(trim.msrp_usd);
  const destination = number(trim.destination_usd);
  const name = record.name?.startsWith(record.brand) ? record.name : `${record.brand} ${record.name}`;

  return <section className="experience-card vehicle-detail">
    <header>
      <h3>{record.model_year} {name}</h3>
      <p className="vehicle-detail-configuration">{trim.name}
        {powertrainLabels[record.powertrain] && ` · ${powertrainLabels[record.powertrain]}`}
      </p>
    </header>
    {color ? <ColorPreview key={color.color_id} record={selected} color={color} />
      : <OverviewPhoto key={trim.trim_id} record={selected} sequence={sequence} asset={hero} />}
    {!color && record.trims.length > 1 && <label className="vehicle-detail-selector">Configuration
      <select value={trim.trim_id} onChange={event =>
        askAboutVehicle('details', record, record.trims.find(item => item.trim_id === event.target.value))}>
        {record.trims.map(item => <option key={item.trim_id} value={item.trim_id}>
          {item.name} · {item.body_style} · {item.drivetrain} · {item.seating_capacity?.split('|').join(' or ')} seats
        </option>)}
      </select>
    </label>}
    <p className="experience-price">{base === null ? 'Unavailable' :
      (Number.isInteger(base) ? wholeDollarPrice.format(base) : price(base))} <small>Base MSRP</small></p>
    {!!facts.length && <ul className="vehicle-detail-facts" aria-label="Key vehicle facts">
      {facts.map(([value, label]) => <li key={label}>
        <strong>{value}</strong><span>{label}</span>
      </li>)}
    </ul>}
    <div className="vehicle-detail-actions">
      {sequence && <button className="vehicle-detail-primary" type="button"
        onClick={() => askAboutVehicle('rotation', record, trim)}>View 360°</button>}
      <button type="button" onClick={() => askAboutVehicle('colors', record, trim)}>
        {color ? 'Change color' : 'Choose a color'}
      </button>
      {!color && <button className={!sequence ? 'vehicle-detail-photo-primary' : undefined} type="button"
        onClick={() => askAboutVehicle('photos', record, trim)}>View photos</button>}
      <button type="button" onClick={() => askAboutVehicle('financing', record, trim)}>Financing</button>
    </div>
    {groups.size
      ? <VehicleSpecs groups={[...groups]} />
      : <p className="experience-note">Verified specifications are unavailable for this configuration.</p>}
    <details className="vehicle-detail-expand"><ReplySummary><strong>Price breakdown</strong></ReplySummary>
      <dl>
        <div><dt>Base MSRP</dt><dd>{price(base)}</dd></div>
        <div><dt>Destination</dt><dd>{price(destination)}</dd></div>
        <div><dt>Base plus destination</dt><dd>{price(base !== null && destination !== null ? base + destination : null)}</dd></div>
        {color && <div><dt>{color.location === 'interior' ? 'Interior material' : 'Paint surcharge'}</dt>
          <dd>{price(color.extra_cost_usd)}</dd></div>}
        <div><dt>Alaska destination</dt><dd>{price(trim.destination_alaska_usd)}</dd></div>
      </dl>
      <p className="experience-note">Paint, options, taxes, title, and dealer fees are additional.</p>
    </details>
  </section>;
}
export function VehicleDetails({ records = [] }) {
  return records.length ? records.map(record => <Details key={record.model_id} record={record} />)
    : <p>Vehicle details are unavailable.</p>;
}

export function comparisonCaption(record, asset) {
  const year = record.model?.model_year;
  const sourceYear = asset?.source_model_year;
  if (asset?.applicability === 'model_reference' || record.image_is_reference) {
    const from = sourceYear || record.image_caption?.match(/^\d{4}/)?.[0];
    const to = year || record.image_caption?.match(/; (\d{4})/)?.[1];
    if (from && to) return `${from} reference · ${to} appearance/equipment may differ`;
  }
  if (asset?.applicability_label) {
    if (!asset.product_trim_code) return `${sourceYear || year || ''} ${record.model?.name || 'model'} · Trim not specified`.trim();
    return '';
  }
  if (/^\d{4} model \/ trim-group reference\b/i.test(record.image_caption || '')) return '';
  return displayCaption(record.image_caption || asset?.caption);
}

export function ComparisonPhoto({ record, showCaption = false, hideCaption = false }) {
  const [failed, setFailed] = useState(false);
  const photos = record.photos || record.assets || [];
  const asset = photos.find(item => item.url === record.image_url) || photos.find(item => item.asset_kind === 'image' && https(item.url) && item.source_field !== 'swatchImageUrl');
  const url = record.image_url || asset?.url;
  if (!url || !https(url) || failed) return <div className="comparison-photo photo-unavailable"><span>Photo unavailable</span><small>Specifications are available below</small></div>;
  const caption = comparisonCaption(record, asset);
  return <figure className="comparison-photo">
    <img src={url} alt={caption || record.model?.name || record.name || 'Vehicle photo'} loading="lazy" referrerPolicy="no-referrer"
      onError={() => setFailed(true)} />
    {!hideCaption && caption && (showCaption || record.image_caption || asset?.applicability_label || asset?.applicability === 'model_reference') &&
      <figcaption>{caption}</figcaption>}
  </figure>;
}

export function specificationNote(value = '') {
  return /^(?:exact configuration|exact trim|trim group[.;]?\s*verify seating-dependent values against exact configuration[.]?|exact trim; retain value qualifiers including seating and charging conditions[.]?)$/i.test(value.trim()) ? '' : value;
}
export function specificationGroup(item) {
  if (item.category.toLowerCase() !== 'specification') return item.category;
  const field = item.field;
  if (/^(?:horsepower_|system_horsepower_|torque_|engine_displacement_|towing_capacity_|curb_weight_)/.test(field)) return 'Performance';
  if (/^(?:charging_level_|battery_capacity_|electric_range_|all_electric_range_|estimated_|range_charge_|mpg_|fuel_tank_|recommended_fuel$)/.test(field)) return 'Efficiency & charging';
  if (/^(?:cargo_|legroom_|front_legroom_|rear_legroom_|height_|length_|wheelbase_|width_|wheel_diameter_)/.test(field)) return 'Dimensions & space';
  return 'Specifications';
}
function factLabel(value) {
  const label = value.replaceAll('_', ' ').trim().toLowerCase()
    .replace(/cubic feet/g, '(cu ft)').replace(/inches|\bin$/g, '(in)').replace(/\blb$/g, '(lb)')
    .replace(/\bmpg\b/g, 'MPG').replace(/\bmpge\b/g, 'MPGe').replace(/\bsae\b/g, 'SAE')
    .replace(/\bepa\b/g, 'EPA').replace(/\baki\b/g, 'AKI').replace(/\bkwh\b/g, 'kWh');
  return label.replace(/^./, letter => letter.toUpperCase());
}

function comparisonBodyStyle(value) {
  return value === 'suv' ? 'SUV' : value?.replace(/^./, letter => letter.toUpperCase());
}

function ComparisonFacts({ rows, records }) {
  return <table className="comparison-facts"><thead><tr><th scope="col">Attribute</th>
    {records.map((record, index) => <th scope="col" key={index}>{record.model?.name || record.name}</th>)}
    </tr></thead><tbody>{rows.map(([label, values]) => <tr key={label}>
      <th scope="row">{label}</th>
      {values.map((value, index) => <td key={records[index].trim_id || index}>{value || 'Not published'}</td>)}
    </tr>)}</tbody></table>;

}

const comparisonMetrics = [
  ['Horsepower', /\b(?:horsepower|hp)\b/i, /horsepower/i],
  ['Torque', /\btorque\b/i, /torque/i],
  ['Fuel economy', /\b(?:mpg|mpge|fuel economy|fuel efficiency|gas mileage)\b/i, /mpg|fuel economy/i],
  ['Electric range', /\b(?:electric|ev) range\b/i, /electric range/i],
  ['Battery capacity', /\b(?:battery capacity|battery size|kwh)\b/i, /battery capacity/i],
  ['Cargo space', /\b(?:cargo|trunk|luggage)\b/i, /cargo volume|^cargo/i],
  ['Legroom', /\blegroom\b/i, /legroom/i],
  ['Towing', /\b(?:tow|towing)\b/i, /tow/i],
  ['Seating', /\b(?:seating|seats|seat count|passenger capacity|third row)\b/i, /^seats \/ rows/i],
  ['Drivetrain', /\b(?:drivetrain|awd|fwd|rwd)\b/i, /^drivetrain$/i],
  ['Transmission', /\btransmission\b/i, /^transmission$/i],
  ['Performance', /\bperformance\b/i, /horsepower|torque|tow/i],
  ['Price', /\b(?:price|pricing|msrp|destination|cheaper|cost)\b/i, /msrp|destination/i],
];

export function CarComparison({ records = [], question = '' }) {
  const [edits, setEdits] = useState({});
  const [featureGroup, setFeatureGroup] = useState('');
  const allFeatures = isFullFeatureComparison(question);
  const picks = records.map(record => ({
    car: { year: record.model?.model_year, name: record.model?.name || record.name },
    trim: record.configuration_choices?.find(trim => trim.trim_id === edits[record.trim_id]) || record,
  }));
  const changed = picks.some(({ trim }, index) => trim.trim_id !== records[index].trim_id);
  records = records.map(record => ({...record, specifications:(record.specifications || []).map(item => ({...item, category:specificationGroup(item)}))}));
  const groups = [...new Set(records.flatMap(record => (record.specifications || []).map(item => item.category)))];
  const summary = [
    ['Base MSRP', records.map(record => price(record.msrp_usd))],
    ['Destination', records.map(record => price(record.destination_usd))],
    ['Body style', records.map(record => record.body_style)],
    ['Seats / rows', records.map(record => [record.seating_capacity, record.seating_rows].filter(Boolean).join(' / '))],
    ['Drivetrain', records.map(record => record.drivetrain)],
    ['Transmission', records.map(record => record.transmission)],
    ['Powertrain', records.map(record => record.model?.powertrain?.replaceAll('_', ' '))],
  ];
  const overviewFields = [
    ['Horsepower · regular 87 AKI', ['horsepower_87_aki', 'HORSEPOWER WITH 87 OCTANE UNLEADED FUEL', 'ENGINE HORSEPOWER WITH REGULAR UNLEADED FUEL', 'system_horsepower_87_octane_spec_deck']],
    ['Horsepower · premium 91 AKI', ['horsepower_91_aki']],
    ['Horsepower · premium 93 AKI', ['horsepower_93_aki']],
    ['Horsepower · premium fuel (octane unspecified)', ['ENGINE HORSEPOWER WITH PREMIUM UNLEADED FUEL']],
    ['Torque · regular 87 AKI (lb-ft)', ['torque_lb_ft_87_aki', 'TORQUE WITH 87 OCTANE UNLEADED FUEL', 'ENGINE TORQUE WITH REGULAR UNLEADED FUEL']],
    ['Torque · premium 91 AKI (lb-ft)', ['torque_lb_ft_91_aki']],
    ['Torque · premium 93 AKI (lb-ft)', ['torque_lb_ft_93_aki']],
    ['City MPG', ['mpg_city']], ['Highway MPG', ['mpg_highway']], ['Combined MPG', ['mpg_combined', 'estimated_combined_mpg_gasoline']],
    ['Combined MPGe · electric and gasoline', ['estimated_combined_mpge_electric_and_gasoline']],
    ['System horsepower · 93 octane (alternate rating)', ['system_horsepower_93_octane_spec_deck']],
    ['Cargo · rows upright (SAE cu ft)', ['cargo_volume_sae_rows_upright_cubic_feet']],
    ['Cargo · third row folded (SAE cu ft)', ['cargo_volume_sae_third_row_folded_cubic_feet']],
    ['Cargo · second / third folded (SAE cu ft)', ['cargo_volume_sae_second_third_rows_folded_cubic_feet']],
    ['Electric range · up to (miles)', ['electric_range_miles_up_to']],
    ['Battery capacity (kWh)', ['battery_capacity_kwh']],
    ['Battery capacity · alternate rating', ['BATTERY CAPACITY']],
    ['Cargo · seats up (SAE cu ft)', ['Cargo volume, rear seatbacks up (SAE, cu ft)']],
    ['Cargo · seats down (SAE cu ft)', ['Cargo volume, rear seatbacks down (SAE, cu ft)']],
    ['Cargo · seats down (EPA cu ft)', [' EPA CARGO VOLUME, REAR SEATBACK DOWN (cu ft)']],
    ['Cargo · seats up / third folded / all rear folded (SAE cu ft)', ['SAE CARGO VOLUME, REAR SEATS UP/3RD ROW FOLDED/2ND AND 3RD ROWS FOLDED (CU FT)']],
  ];
  const additionalFacts = [];
  for (const [label, aliases] of overviewFields) {
    const matches = records.map(record => {
      const specs = record.specifications || [];
      const direct = specs.filter(item => aliases.includes(item.field));
      if (direct.length || !['City MPG', 'Highway MPG'].includes(label)) return direct;
      const combined = specs.find(item => item.field === 'AWD, AUTOMATIC TRANSMISSION (MPG, CITY/HWY)');
      const pair = combined?.value.match(/^\s*(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)\s*$/);
      return pair ? [{...combined, value:pair[label === 'City MPG' ? 1 : 2]}] : [];
    });
    const destination = /premium|other rating|alternate rating|seats down|third row folded|second \/ third folded|seats up \/ third folded/.test(label) ? additionalFacts : summary;
    if (matches.some(items => items.length)) destination.push([label, matches.map((items, recordIndex) => items.length ? items.map((item, index) =>
      <span key={index} className="spec-value">
        {specValue(item)}{/horsepower/i.test(label) && /^\d+(?:\.\d+)?$/.test(item.value) ? ' hp' : ''}
        {/horsepower/i.test(label) && records[recordIndex].model?.powertrain === 'plug_in_hybrid' &&
          <small>Combined system output</small>}
        {specificationNote(item.applicability) && <small>{specificationNote(item.applicability)}</small>}
      </span>) : null)]);
  }
  const fields = [...new Set(records.flatMap(record => record.specifications.map(item => item.field)))];
  const normalize = value => value.toLowerCase().replaceAll(/[^a-z0-9]+/g, ' ').trim();
  const request = ` ${normalize(question)} `;
  const exactFields = fields.filter(field => normalize(field).length >= 4 &&
    request.includes(` ${normalize(field)} `));
  const metrics = comparisonMetrics.filter(([, match]) => match.test(question));
  const focus = allFeatures ? [] : metrics.length ? metrics.map(([label]) => label) : exactFields.map(factLabel);
  const overview = [...summary, ...additionalFacts];
  function comparisonRowsForFields(selectedFields) {
    return selectedFields.map(field => [factLabel(field), records.map(record =>
      record.specifications.find(item => item.field === field)?.value)]);
  }
  const focusedRows = metrics.length ? metrics.flatMap(([label, , match]) => {
    const rows = overview.filter(([name]) => match.test(name));
    if (rows.length) return rows;
    const matchingFields = fields.filter(field => match.test(factLabel(field)));
    return matchingFields.length ? comparisonRowsForFields(matchingFields) : [[label, records.map(() => null)]];
  }) : comparisonRowsForFields(exactFields);
  const formatComparisonPrice = value => {
    const amount = number(value);
    return Number.isInteger(amount) ? wholeDollarPrice.format(amount) : price(value);
  };
  function rowsForGroup(group) {
    const groupFields = [...new Set(records.flatMap(record => record.specifications
      .filter(item => item.category === group).map(item => item.field)))];
    return groupFields.map(field => [factLabel(field), records.map(record => {
      const facts = record.specifications.filter(item => item.category === group && item.field === field);
      return facts.length ? facts.map((item, index) => <span className="spec-value" key={index}>
        {specValue(item)}{specificationNote(item.applicability) && <small>{specificationNote(item.applicability)}</small>}
      </span>) : null;
    })]);
  }
  const keyFeatures = groups.find(group => /^key features$/i.test(group));
  const sharedKeyFeatures = allFeatures && keyFeatures &&
    rowsForGroup(keyFeatures).some(([, values]) => values.every(Boolean));
  const activeGroup = featureGroup || (sharedKeyFeatures ? keyFeatures : 'overview');
  return <section className="vehicle-comparison">
    <header className="comparison-result-heading">
      <h3>{allFeatures ? 'Feature comparison' : focus.length ? `${focus.join(' & ')} comparison` : 'Your comparison'}</h3>
      <button type="button" className="comparison-edit"
        onClick={() => askShoppingQuestion('Show all 2027 Mazda models.', true)}>Change cars</button>
    </header>
    {allFeatures ? <section className="comparison-feature-browser">
      <label>Feature category
        <select value={activeGroup} onChange={event => setFeatureGroup(event.target.value)}>
          <option value="overview">Overview</option>
          {groups.map(group => <option key={group} value={group}>{factLabel(group)}</option>)}
        </select>
      </label>
      <ComparisonFacts rows={activeGroup === 'overview' ? overview.slice(2) : rowsForGroup(activeGroup)} records={records} />
    </section> : focusedRows.length > 0 && <ComparisonFacts rows={focusedRows} records={records} />}
    <div className="comparison-models">
      {records.map((record, index) => <div key={record.model?.name + index}>
        <ComparisonPhoto key={record.trim_id} record={record} showCaption />
        <h4>{record.model?.model_year} {record.model?.name || record.name}</h4>
        <p className="comparison-configuration">{[record.name, comparisonBodyStyle(record.body_style),
          record.drivetrain].filter(Boolean).join(' · ')}</p>
        {record.configuration_choices?.length > 1 && <details className="comparison-trim-edit">
          <ReplySummary>Change trim<span className="comparison-visually-hidden"> for {record.model?.name}</span></ReplySummary>
          <select aria-label={`Trim for ${record.model?.name}`} value={picks[index].trim.trim_id}
            onChange={event => {
              const id = event.target.value;
              setEdits(current => ({ ...current, [record.trim_id]: id }));
            }}>
            {record.configuration_choices.map(trim => <option key={trim.trim_id} value={trim.trim_id}>
              {[trim.name, comparisonBodyStyle(trim.body_style), trim.drivetrain,
                trim.seating_capacity && `${trim.seating_capacity.replaceAll('|', ' or ')} seats`]
                .filter(Boolean).join(' · ')}
            </option>)}
          </select>
        </details>}
      </div>)}
    </div>
    {changed && <button className="comparison-edit compare-revised" type="button"
      onClick={() => askToCompare(picks, allFeatures ? 'all features' : focus.join(' and ').toLowerCase())}>Compare cars</button>}
    {!allFeatures && !focus.length && <dl className="comparison-costs" aria-label="Comparison pricing">
      {[['Base MSRP', 'msrp_usd'], ['Destination', 'destination_usd']].map(([label, field]) =>
        <div key={field}><dt>{label}</dt>{records.map((record, index) =>
          <dd key={record.trim_id || index}>
            <span className="comparison-visually-hidden">{record.model?.name || record.name}: </span>
            {formatComparisonPrice(record[field])}
          </dd>)}</div>)}
    </dl>}
    {!allFeatures && <details className="comparison-group comparison-all-specs"><ReplySummary>Features &amp; specs</ReplySummary>
    <ComparisonFacts rows={summary.slice(2)} records={records} />
    {additionalFacts.length > 0 && <details className="comparison-group"><ReplySummary>More performance and space</ReplySummary><ComparisonFacts rows={additionalFacts} records={records} /></details>}
    {groups.map(group => {
      const rows = rowsForGroup(group);
      return <details className="comparison-group" key={group}>
        <ReplySummary>{factLabel(group)} <span>{rows.length} attributes</span></ReplySummary>
        <ComparisonFacts rows={rows} records={records} />
      </details>;
    })}
    <p className="experience-note">Trim-group specifications may vary with seating. Verify the exact configuration.</p>
    </details>}
  </section>;
}

export function loanPayment(principal, apr, months) {
  if (!Number.isFinite(principal) || principal < 0 || !Number.isFinite(apr) || apr < 0 ||
      apr > 100 || !Number.isInteger(months) || months < 1 || months > 120) return null;
  const rate = apr / 1200;
  return rate === 0 ? principal / months : principal * rate / -Math.expm1(-months * Math.log1p(rate));
}

function PaymentCalculator({ defaults, priceBasis }) {
  const [values, setValues] = useState(defaults);
  const amount = number(values.amount), down = number(values.down);
  const principal = amount !== null && down !== null && down >= 0 && down <= amount ? amount - down : null;
  const estimate = principal === null ? null : loanPayment(principal, number(values.apr), number(values.months));
  return <section className="payment-calculator">
    <h3>Estimate your payment</h3>
    <p className="experience-note">{priceBasis === 'Starting MSRP' ? 'Uses the model’s starting MSRP. '
      : priceBasis ? `Uses the ${priceBasis} trim’s MSRP. ` : ''}
      Adjust any field. Taxes and fees are excluded unless included in your price.</p>
    <div className="calculator-inputs">
      {[['amount', 'Vehicle price ($)'], ['down', 'Down payment ($)'], ['apr', 'APR (%)'], ['months', 'Term (months)']].map(([key, label]) =>
        <label key={key}>{label}<input type="number" min={key === 'months' ? 1 : 0}
          max={key === 'apr' ? 100 : key === 'months' ? 120 : undefined}
          step={key === 'months' ? 1 : '0.01'} inputMode="decimal" value={values[key]}
          onChange={event => setValues(current => ({ ...current, [key]: event.target.value }))} /></label>)}
    </div>
    <div aria-live="polite">{estimate === null
      ? <p>Enter valid amounts, APR from 0–100%, and a whole-number term from 1–120 months. Down payment must not exceed price.</p>
      : <><p className="experience-price">{price(estimate)} <small>/ month estimate</small></p>
        <p>Amount financed {price(principal)} · Total interest {price(estimate * Number(values.months) - principal)}</p></>}
    </div>
    <p className="experience-note">Illustration only. Approval, available rates, and final terms require lender confirmation.</p>
  </section>;
}
export function FinancingOffers({ records = [] }) {
  const publishedApr = records.find(record => record.offer_type === 'apr' &&
    record.expiry_status === 'within_recorded_expiry' && number(record.apr_percent) !== null);
  const priceRecord = publishedApr ?? records[0];
  const defaults = {
    amount: priceRecord?.vehicle_price_usd ?? '',
    down: '0',
    apr: publishedApr?.apr_percent ?? '',
    months: publishedApr?.term_months_max ?? '',
  };
  return <section className="experience-card">
    <h3>Published financing information</h3>
    {!records.length && <p>Verified offer terms are unavailable for this selection.</p>}
    {records.map(record => <section className="offer" key={record.offer_id}>
      <h4>{record.model_year} · {record.offer_type.replaceAll('_', ' ')}</h4>
      {record.offer_type === 'apr' && <p className="experience-price">
        {number(record.apr_percent) === null ? 'APR unavailable' : `${record.apr_percent}% APR`}
        <small> Up to {record.term_months_max || 'unverified'} months</small>
      </p>}
      {record.cash_amount_usd && <p>{price(record.cash_amount_usd)} cash incentive</p>}
      {record.lease_monthly_usd && <p>{price(record.lease_monthly_usd)} / month lease · {price(record.lease_due_at_signing_usd)} due at signing</p>}
      <p className="offer-status">{(record.expiry_status || 'availability_unknown').replaceAll('_', ' ')} as of {record.as_of || 'unknown date'}</p>
      <p>Expires {record.expires_on || 'date unavailable'}</p>
      <p>{record.eligibility}</p>
      <details><ReplySummary>Full offer details</ReplySummary><p>{record.geography}</p><p>{record.dealer_states}</p><p>{record.combinability}</p></details>
    </section>)}
    <PaymentCalculator defaults={defaults} priceBasis={priceRecord?.vehicle_price_basis} />
  </section>;
}
