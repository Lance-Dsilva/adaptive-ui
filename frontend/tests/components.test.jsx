import './visualization.test.jsx';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import * as components from '../src/VehicleExperience.jsx';
import { comparisonFollowup } from '../src/vehiclePrompts.js';

const fixtures = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const { loanPayment } = components;

for (const { component, records, model } of fixtures) {
  test(`${component} renders actual ${model} catalog data`, () => {
    const html = renderToStaticMarkup(React.createElement(components[component], { records }));
    assert.ok(html.length > 40);
    assert.ok(!html.includes('NaN') && !html.includes('Infinity'));
    assert.doesNotMatch(html, /(?:>[^<>]*\bsources?\b[^<>]*<|aria-label="Source:|Checked 20\d\d)/i);
    if (component === 'VehicleVisualization') {
      const available = records.some(record => components.verifiedSequences(record).length);
      assert.ok(html.includes(available ? 'Drag to rotate' : '360° view is unavailable'));
    }
  });
}

for (const component of new Set(fixtures.map(fixture => fixture.component))) {
  test(`${component} renders empty records`, () => {
    const html = renderToStaticMarkup(React.createElement(components[component], { records: [] }));
    assert.ok(html.length > 0);
  });
}

test('payment matches zero APR and amortized reference values', () => {
  assert.equal(loanPayment(12000, 0, 12), 1000);
  assert.equal(loanPayment(0, 5, 60), 0);
  assert.ok(Math.abs(loanPayment(30000, 6, 60) - 579.9840458828) < 1e-8);
});

test('near-zero positive APR stays finite and converges to the zero-APR payment', () => {
  const payment = loanPayment(12000, 1e-14, 12);
  assert.ok(Number.isFinite(payment));
  assert.ok(Math.abs(payment - 1000) < 1e-8);
  assert.equal(loanPayment(0, 1e-14, 12), 0);
});

test('payment rejects invalid inputs', () => {
  for (const args of [
    [-1, 5, 60], [1000, -1, 60], [1000, 101, 60], [1000, 5, 0],
    [1000, 5, 121], [1000, 5, 12.5], [NaN, 5, 12], [1000, Infinity, 12],
    ['1000', 5, 12],
  ]) {
    assert.equal(loanPayment(...args), null, JSON.stringify(args));
  }
});

test('detail visualizer action remains available with truthful per-model availability', () => {
  for (const fixture of fixtures.filter(item => item.component === 'VehicleDetails')) {
    const html = renderToStaticMarkup(React.createElement(components.VehicleDetails, { records: fixture.records }));
    assert.ok(html.includes('View photos'));
    assert.ok(!html.includes('Rotate exterior photos'));
    assert.ok(!html.includes('Explore visualization'));
    const hasOverviewRotation = fixture.records.some(record => {
      const trim = record.trims.find(item => item.trim_id === record.selected_trim_id) || record.trims[0];
      return trim && components.verifiedSequences({ ...record, trims: [trim] }).length;
    });
    assert.equal(html.includes('View 360°'), hasOverviewRotation);
    for (const record of fixture.records) {
      const sequences = components.verifiedSequences(record);
      const published = (record.visualizations || []).filter(item => item.status === 'verified_frames');
      assert.equal(sequences.length, published.length);
      for (const sequence of sequences) {
        assert.equal(sequence.model_id, record.model_id);
        assert.ok(record.trims.some(trim => trim.product_trim_code === sequence.product_trim_code));
        assert.ok(sequence.frames.length > 1);
        assert.equal(new Set(sequence.frames).size, sequence.frames.length);
        assert.ok(sequence.frames.every(url => url.startsWith('/assets/vehicle-rotations/')));
        assert.ok(sequence.source_url.startsWith('https://www.mazdausa.com/'));
        assert.ok(sequence.caption.includes('Representative exterior preview'));
        assert.ok(record.colors.some(color => color.color_code === sequence.color_code && color.product_trim_code === sequence.product_trim_code));
      }
      if (record.model_id === 'us-2027-cx5') {
        const original = sequences.find(item => item.visualization_id === '27CX525S-51K');
        assert.equal(original.frames.length, 48);
        assert.equal(original.color_code, '51K');
      }
    }
  }
});

test('exact-model photos exclude family references, other trims, swatches and changed years', () => {
  const exact = {
    asset_kind: 'image', source_field: 'trim_image',
    model_id: 'model-a', source_model_year: '2027', product_trim_code: 'trim-a',
    url: 'https://example.invalid/exact.png?angle=1&angle=2',
  };
  const record = {
    model_id: 'model-a', model_year: '2027', trims: [{ product_trim_code: 'trim-a' }],
    assets: [
      exact, { ...exact },
      { ...exact, model_id: '', url: 'https://example.invalid/family.png' },
      { ...exact, model_id: 'model-b', url: 'https://example.invalid/other-model.png' },
      { ...exact, product_trim_code: 'trim-b', url: 'https://example.invalid/other-trim.png' },
      { ...exact, source_model_year: '2026', url: 'https://example.invalid/prior-year.png' },
      { ...exact, source_field: 'swatchImageUrl', url: 'https://example.invalid/swatch.png' },
    ],
  };
  assert.deepEqual(components.vehiclePhotos(record), [exact]);
});

test('PHEV gallery shows absent exact imagery instead of using family photos', () => {
  const fixture = fixtures.find(item => item.component === 'VehicleGallery' && item.model === 'us-2027-cx90-phev');
  const records = fixture.records.map(record => ({...record, assets:record.assets.filter(asset => asset.applicability !== 'model_reference')}));
  const html = renderToStaticMarkup(React.createElement(components.VehicleGallery, { records }));
  assert.ok(html.includes('Photo unavailable for this selection'));
  assert.ok(!html.includes('<img'));
});

test('rotation requires explicitly verified distinct applicable frames', () => {
  const sequence = {
    visualization_id: 'spin', model_id: 'model-a', product_trim_code: 'trim-a',
    status: 'verified_frames',
    frame_urls_json: JSON.stringify(['https://example.invalid/1.png', 'https://example.invalid/2.png']),
  };
  const record = { model_id: 'model-a', trims: [{ product_trim_code: 'trim-a' }] };
  assert.equal(components.verifiedSequences({ ...record, visualizations: [sequence] }).length, 1);
  for (const invalid of [
    { ...sequence, status: 'directory_observed_frames_not_resolved' },
    { ...sequence, product_trim_code: 'trim-b' },
    { ...sequence, model_id: 'model-b' },
    { ...sequence, frame_urls_json: 'invalid' },
    { ...sequence, frame_urls_json: '["https://example.invalid/1.png","https://example.invalid/1.png"]' },
    { ...sequence, frame_urls_json: '["javascript:alert(1)","https://example.invalid/2.png"]' },
  ]) {
    assert.deepEqual(components.verifiedSequences({ ...record, visualizations: [invalid] }), []);
  }
});

test('photo captions never derive visual descriptions from filenames', () => {
  const record = {
    model_id: 'model-a', name: 'Model A', model_year: '2027',
    trims: [{ trim_id: 'a', product_trim_code: 'a', name: 'Trim A' }],
    assets: [{
      model_id: 'model-a', source_model_year: '2027', product_trim_code: 'a',
      asset_kind: 'image', source_field: 'trim_image', filename_year_hint: '1999',
      url: 'https://example.invalid/1999-red-car-front.png',
    }],
  };
  const html = renderToStaticMarkup(React.createElement(components.VehicleGallery, { records: [record] }));
  assert.ok(html.includes('alt="Vehicle reference image"'));
  assert.ok(!html.includes('Filename indicates'));
});

test('display captions retain human wording and hide image path metadata', () => {
  assert.equal(components.displayCaption('Mazda CX-5 front three-quarter view'), 'Mazda CX-5 front three-quarter view');
  assert.equal(components.displayCaption('Exterior / interior comparison'), 'Exterior / interior comparison');
  assert.equal(components.displayCaption('Front/rear views'), 'Front/rear views');
  for (const caption of [
    null, '', '   ', 'front.png', 'exterior/front.png', '/content/dam/front.png',
    'https://example.invalid/image?view=front', 'exterior/rhodium-white/front',
    'C:\\vehicle\\front.webp', 'images/front.JPG?width=600',
  ]) {
    assert.equal(components.displayCaption(caption), 'Vehicle reference image');
  }
});

test('photo uses the filtered caption for both visible text and alt without mutating assets', () => {
  const asset = {
    model_id: 'model-a', source_model_year: '2027', product_trim_code: 'a',
    asset_kind: 'image', source_field: 'trim_image',
    caption: 'exterior/rhodium-white/front.png', url: 'https://example.invalid/photo.png',
  };
  const record = {
    model_id: 'model-a', model_year: '2027', name: 'Model A',
    trims: [{ trim_id: 'a', product_trim_code: 'a', name: 'Trim A' }],
    assets: [asset],
  };
  const html = renderToStaticMarkup(React.createElement(components.VehicleGallery, { records: [record] }));
  assert.ok(html.includes('alt="Vehicle reference image"'));
  assert.ok(html.includes('<figcaption>Vehicle reference image'));
  assert.ok(!html.includes(asset.caption));
  assert.equal(asset.caption, 'exterior/rhodium-white/front.png');
});

import { ResponseBlocks, previousTurnsFor, responseText, turnContext } from '../src/ResponseBlocks.jsx';

test('discovery merges year and body scope into the compact toolbar and shows reset only for applied filters', () => {
  const cars = [{
    id: 'cx5', name: 'Mazda CX-5', year: 2027, msrp: 29990, powertrain: 'gasoline', trims: [],
  }];
  const catalog = {type: 'ui', component: 'CarList', props: {cars}};
  const context = {type: 'context', items: ['2027', 'SUVs']};
  const initial = renderToStaticMarkup(<ResponseBlocks blocks={[context, catalog]} />);
  assert.match(initial, /2027 Mazda SUVs<\/h3><span>1 model/);
  assert.match(initial, /class="catalog-filters"/);
  assert.doesNotMatch(initial, /Response context|Clear filters/);
  const applied = renderToStaticMarkup(<ResponseBlocks blocks={[
    {...context, items: [...context.items, 'Up to $35,000 MSRP', 'Hybrid']}, catalog,
    {type: 'actions', actions: [{id: 'clear-budget', message: 'Remove budget', label: 'Clear budget'}]},
  ]} />);
  assert.match(applied, /aria-label="Applied filters"/);
  assert.match(applied, /Up to \$35,000 MSRP/);
  assert.match(applied, /Clear filters/);
  assert.doesNotMatch(applied, /Clear budget|Response context/);
});

test('financing estimator uses selected MSRP and a valid published zero APR', () => {
  const record = {
    offer_id: 'apr', model_year: 2027, offer_type: 'apr', vehicle_price_usd: '32140',
    vehicle_price_basis: '2.5 S Select', apr_percent: '0', term_months_max: '36',
    expiry_status: 'within_recorded_expiry',
  };
  const html = renderToStaticMarkup(<ResponseBlocks blocks={[{
    type: 'ui', component: 'FinancingOffers', props: { records: [record] },
  }]} />);
  assert.match(html, /Vehicle price \(\$\)<input[^>]*value="32140"/);
  assert.match(html, /APR \(%\)<input[^>]*value="0"/);
  assert.match(html, /Term \(months\)<input[^>]*value="36"/);
  assert.match(html, /month estimate/);
  const expired = renderToStaticMarkup(<ResponseBlocks blocks={[{
    type: 'ui', component: 'FinancingOffers',
    props: { records: [{ ...record, expiry_status: 'expired' }] },
  }]} />);
  assert.match(expired, /APR \(%\)<input[^>]*value=""/);
});

test('web replies format inline emphasis and keep publisher links clickable', () => {
  const html = renderToStaticMarkup(<ResponseBlocks blocks={[{
    type: 'text', role: 'answer', text: 'The RX-7 launched in **March 1978**.',
    citations: [{ url: 'https://www.mazda.com/history', label: 'mazda.com' }],
  }]} />);
  assert.match(html, /<strong>March 1978<\/strong>/);
  assert.match(html, /<a href="https:\/\/www\.mazda\.com\/history"[^>]*> mazda\.com<\/a>/);
});

test('response roles determine typography independently of position and retain adjacent block order', () => {
  const blocks = [
    { type: 'text', id: 'body-first', role: 'body', text: 'Opening body' },
    { type: 'context', id: 'scope', items: ['2027', 'SUVs'] },
    { type: 'text', id: 'answer', role: 'answer', text: 'The main answer' },
    { type: 'ui', id: 'unsupported', component: 'Unknown', fallback_text: 'Vehicle fallback' },
    { type: 'text', id: 'notice', role: 'notice', text: 'Price notice' },
    { type: 'disclosure', id: 'source', title: 'Research details', text: 'Model years and coverage' },
    { type: 'text', id: 'legacy', text: 'Legacy body' },
    { type: 'text', id: 'unknown-role', role: 'custom', text: 'Unknown role body' },
    { type: 'text', id: 'status', role: 'status', text: 'Status message' },
  ];
  const html = renderToStaticMarkup(<ResponseBlocks blocks={blocks} />);
  assert.ok(html.includes('class="response-body">Opening body'));
  assert.ok(html.includes('class="response-answer">The main answer'));
  assert.ok(html.includes('class="response-notice">Price notice'));
  assert.ok(html.includes('class="response-body">Legacy body'));
  assert.ok(html.includes('class="response-body">Unknown role body'));
  assert.ok(html.includes('role="status">Status message'));
  assert.ok(html.includes('<details class="response-disclosure"><summary>Research details</summary>'));
  const ordered = ['Opening body', 'Response context', 'The main answer', 'Vehicle fallback', 'Price notice', 'Research details', 'Legacy body'];
  for (let index = 1; index < ordered.length; index++) {
    assert.ok(html.indexOf(ordered[index - 1]) < html.indexOf(ordered[index]));
  }
  assert.ok(!html.includes('<button'));
});

test('response actions preserve action payloads and allow at most two buttons', () => {
  const actions = [
    { id: 'explore', label: 'Explore SUVs', request: { intent: 'browse', filters: { body_style: 'suv' } } },
    { id: 'compare', label: 'Compare models', request: { intent: 'browse', compare: true } },
    { id: 'extra', label: 'Extra', request: { intent: 'test_drive' } },
    { id: 'legacy', label: 'Legacy text prompt', message: 'Show all Mazda models' },
  ];
  let received;
  const blocks = [{ type: 'actions', id: 'next', actions }];
  const elements = ResponseBlocks({ blocks, onAction: action => { received = action; } }).props.children;
  const buttons = elements[0].props.children;
  assert.equal(buttons.length, 2);
  buttons[1].props.onClick();
  assert.equal(received, actions[1]);
  const html = renderToStaticMarkup(<ResponseBlocks blocks={blocks} onAction={() => {}} disabled />);
  assert.equal((html.match(/disabled=""/g) || []).length, 2);
  assert.ok(!html.includes('Extra'));
  const choices = renderToStaticMarkup(<ResponseBlocks blocks={[
    {...blocks[0], choice: true},
  ]} onAction={() => {}} />);
  assert.ok(choices.includes('Extra'));
  assert.ok(!choices.includes('Legacy text prompt'));
});

test('inactive replies retain their content and disable card and disclosure controls', () => {
  const { records } = fixtures.find(item =>
    item.model === 'us-2027-cx5' && item.component === 'VehicleVisualization');
  const blocks = [
    { type: 'text', text: 'Here is the exterior.' },
    { type: 'disclosure', title: 'Coverage', text: 'Published configurations' },
    { type: 'ui', component: 'VehicleVisualization', props: { records } },
  ];
  const active = renderToStaticMarkup(<ResponseBlocks blocks={blocks} />);
  const inactive = renderToStaticMarkup(<ResponseBlocks blocks={blocks} disabled />);
  assert.match(active, /<fieldset class="reply-controls">/);
  assert.match(inactive, /<fieldset class="reply-controls" disabled="">/);
  assert.match(inactive, /<summary aria-disabled="true" tabindex="-1">Coverage/);
  assert.match(inactive, /class="rotation-stage" tabindex="-1" role="group" aria-disabled="true"/);
  assert.match(inactive, /Here is the exterior/);
  assert.match(inactive, /Published configurations/);
});

test('response actions and retries bind history to the originating turn', () => {
  const turns = [
    { id: 0, message: 'Mazda SUVs', blocks: [{ type: 'text', text: 'SUV results' }] },
    { id: 1, message: 'Under $35,000', blocks: [{ type: 'text', text: 'One model' }] },
    { id: 2, message: 'Compare sedans', blocks: [{ type: 'text', text: 'Later discussion' }] },
    { id: 3, message: 'Failed request' },
  ];
  assert.deepEqual(previousTurnsFor(turns, 4, 1).map(turn => turn.id), [0, 1]);
  assert.deepEqual(previousTurnsFor(turns, 5, 1).map(turn => turn.id), [0, 1]);
  assert.deepEqual(previousTurnsFor(turns, 4).map(turn => turn.id), [0, 1, 2]);
  assert.deepEqual(previousTurnsFor(turns, 0, 0), []);
});

test('typed follow-ups receive the full catalog scope after a filter button', () => {
  const turn = { message: 'Up to $35,000', request: { intent: 'browse' }, blocks: [
    { type: 'context', items: ['2027', 'SUVs', 'AWD', 'Up to $35,000 MSRP'] },
  ] };
  assert.equal(turnContext(turn), '2027 · SUVs · AWD · Up to $35,000 MSRP');
  assert.equal(turnContext({ message: 'What about cargo?', blocks: [] }), 'What about cargo?');
});

test('transcript includes readable ordered content and omits suggested messages', () => {
  assert.equal(responseText([
    { type: 'text', role: 'answer', text: 'Answer' },
    { type: 'context', items: ['2027', 'SUV'] },
    { type: 'ui', fallback_text: 'Car list' },
    { type: 'actions', actions: [{ message: 'Never said by the customer' }] },
    { type: 'disclosure', title: 'Details', text: 'Coverage information' },
  ]), 'Answer\n2027 · SUV\nCar list\nCoverage information');
});

test('supplemental UI does not duplicate the curator’s answer in history or on fallback', () => {
  const blocks = [
    { type: 'text', text: 'The requested rate is unverified.' },
    { type: 'ui', component: 'UnknownCard', fallback_text: 'The requested rate is unverified.' },
  ];
  assert.equal(responseText(blocks), 'The requested rate is unverified.');
  const html = renderToStaticMarkup(<ResponseBlocks blocks={blocks} />);
  assert.equal(html.match(/The requested rate is unverified\./g).length, 1);
});

test('comparison uses semantic headers and retains full specification values', () => {
  const record = {trim_id: 'one', name: 'Trim A', model: {name: 'Model A'}, msrp_usd: '32000',
    specifications: [{category: 'Performance',field: 'horsepower_87_aki',value: '280 hp',applicability: 'Regular fuel',source_url: 'https://example.com/spec.pdf'},
      {category: 'Safety',field: 'Connected services',value: 'Subscription required'}]};
  const html = renderToStaticMarkup(<components.CarComparison records={[record, {...record, trim_id:'two', model:{name:'Model B'}}]} />);
  assert.ok(html.includes('scope="col"') && html.includes('scope="row"'));
  assert.ok(html.includes('Horsepower · regular 87 AKI'));
  assert.ok(html.includes('Subscription required'));
  assert.ok(!html.includes('https://example.com/spec.pdf'));
});

test('all features keeps the active trims and shows their feature categories before pricing', () => {
  const records = [
    { trim_id: 'turbo-preferred', name: 'Turbo Preferred', model: { name: 'CX-90 Inline 6 Turbo' },
      specifications: [{ category: 'key features', field: 'Seat material', value: 'Leather' }] },
    { trim_id: 'phev-preferred', name: 'PHEV Preferred', model: { name: 'CX-90 Plug-in Hybrid' },
      specifications: [{ category: 'key features', field: 'Seat material', value: 'Leatherette' }] },
  ];
  const block = { type: 'ui', component: 'CarComparison', props: { records, question: 'Compare all features' } };
  assert.deepEqual(comparisonFollowup('Compare all features', [block]), {
    intent: 'comparison', trim_ids: ['turbo-preferred', 'phev-preferred'], focus: 'all features',
  });
  assert.equal(comparisonFollowup('Compare all features of the CX-5 and Mazda3', [block]), null);
  const html = renderToStaticMarkup(<ResponseBlocks blocks={[block]} />);
  const firstView = html.slice(0, html.indexOf('class="comparison-models"'));
  assert.ok(firstView.includes('Feature category') && firstView.includes('Seat material'));
  assert.ok(firstView.includes('Leather') && firstView.includes('Leatherette'));
  assert.ok(!html.includes('Comparison pricing'));
  const partial = renderToStaticMarkup(<components.CarComparison question="Compare all features"
    records={[records[0], { ...records[1], specifications: [] }]} />);
  assert.match(partial, /value="overview" selected="">Overview/);
});

test('engine specs follow-up keeps the exact trims and puts engine data first', () => {
  const records = [
    { trim_id: 'cx5-base', name: '2.5 S', model: { name: 'CX-5' }, msrp_usd: '29990',
      specifications: [
        { category: 'Engine', field: 'ENGINE TYPE', value: '2.5L four-cylinder' },
        { category: 'Engine', field: 'DISPLACEMENT (CC)', value: '2488' },
        { category: 'Engine', field: 'HORSEPOWER WITH 87 OCTANE UNLEADED FUEL', value: '187 hp' },
        { category: 'Engine', field: 'TORQUE WITH 87 OCTANE UNLEADED FUEL', value: '186 lb-ft' },
      ] },
    { trim_id: 'cx90-select', name: '3.3 Turbo Select', model: { name: 'CX-90 Inline 6 Turbo' },
      specifications: [
        { category: 'Engine', field: 'ENGINE TYPE', value: '3.3L turbo inline-six' },
        { category: 'Engine', field: 'ENGINE HORSEPOWER WITH REGULAR UNLEADED FUEL', value: '280 hp' },
        { category: 'Engine', field: 'ENGINE TORQUE WITH REGULAR UNLEADED FUEL', value: '332 lb-ft' },
        { category: 'Motor', field: 'HORSEPOWER', value: '16.6 hp' },
      ] },
  ];
  const block = { type: 'ui', component: 'CarComparison', props: { records, question: 'engine specs' } };
  const action = { intent: 'comparison', trim_ids: ['cx5-base', 'cx90-select'], focus: 'engine specs' };
  assert.deepEqual(comparisonFollowup('Compare engine specs', [block]), action);
  assert.deepEqual(comparisonFollowup('Compare their engines?', [block]), action);
  assert.equal(comparisonFollowup('Compare engine specs for the CX-5 and Mazda3', [block]), null);
  assert.equal(comparisonFollowup('Compare engine specs', []), null);
  const html = renderToStaticMarkup(<ResponseBlocks blocks={[block]} />);
  const firstView = html.slice(0, html.indexOf('class="comparison-models"'));
  for (const text of ['Engine comparison', '2.5L four-cylinder', '3.3L turbo inline-six', '2488 cc',
    '187 hp', '280 hp', '186 lb-ft', '332 lb-ft']) {
    assert.ok(firstView.includes(text), text);
  }
  assert.ok(!firstView.includes('16.6 hp'));
  assert.ok(!html.includes('Comparison pricing'));
});

test('natural engine and mileage follow-up compares published MPG for the selected trims', () => {
  const specs = entries => entries.map(([field, value]) => ({ category: 'specification', field, value }));
  const records = [
    { trim_id: 'mazda3-sedan', name: '2.5 S', model: { name: 'Mazda3' },
      specifications: specs([['engine_displacement_l', '2.5'], ['horsepower_87_aki', '186'],
        ['mpg_city', '27'], ['mpg_highway', '36'], ['mpg_combined', '30']]) },
    { trim_id: 'cx5-suv', name: '2.5 S', model: { name: 'CX-5' },
      specifications: specs([['DISPLACEMENT (CC)', '2488'], ['HORSEPOWER WITH 87 OCTANE UNLEADED FUEL', '187 hp'],
        ['AWD, AUTOMATIC TRANSMISSION (MPG, CITY/HWY)', '24 / 30']]) },
  ];
  const question = 'Can you compare all engine details like mileage etc';
  const block = { type: 'ui', component: 'CarComparison', props: { records, question } };
  const action = comparisonFollowup(question, [block]);
  assert.deepEqual(action, { intent: 'comparison', trim_ids: ['mazda3-sedan', 'cx5-suv'],
    focus: 'engine specs and fuel economy' });
  assert.equal(comparisonFollowup(question + ' for the CX-90 and CX-5', [block]), null);
  assert.equal(comparisonFollowup('Compare mileage', [block]).focus, 'fuel economy');
  for (const focus of [question, action.focus]) {
    const html = renderToStaticMarkup(<ResponseBlocks blocks={[{ ...block, props: { records, question: focus } }]} />);
    const featured = html.slice(0, html.indexOf('class="comparison-models"'));
    assert.match(featured, /Engine &amp; fuel economy comparison/);
    assert.match(featured, /City MPG.*?>27<.*?>24</);
    assert.match(featured, /Highway MPG.*?>36<.*?>30</);
    assert.match(featured, /Combined MPG.*?>30<.*?>Not published</);
    assert.ok(featured.includes('186 hp') && featured.includes('187 hp'));
    assert.ok(!html.includes('Comparison pricing'));
  }
});

test('all engine features keeps the selected plug-in hybrid and compares its published powertrain data', () => {
  const specs = entries => entries.map(([field, value]) => ({ category: 'specification', field, value }));
  const records = [
    { trim_id: 'cx5-base', name: '2.5 S', model: { name: 'CX-5', powertrain: 'gasoline' },
      specifications: specs([['REDLINE', '6,500 rpm'], ['TORQUE WITH 87 OCTANE UNLEADED FUEL', '186 lb-ft']]) },
    { trim_id: 'cx90-phev-preferred', name: 'PHEV Preferred',
      model: { name: 'CX-90 Plug-in Hybrid', powertrain: 'plug_in_hybrid' },
      specifications: specs([['battery_capacity_kwh', '17.8'], ['electric_range_miles_up_to', '27'],
        ['horsepower_91_aki', '323'], ['torque_lb_ft_91_aki', '369'],
        ['estimated_combined_mpg_gasoline', '26'], ['estimated_combined_mpge_electric_and_gasoline', '56']]) },
  ];
  const question = 'Compare all engine features';
  const block = { type: 'ui', component: 'CarComparison', props: { records, question } };
  const action = comparisonFollowup(question, [block]);
  assert.deepEqual(action, { intent: 'comparison', trim_ids: ['cx5-base', 'cx90-phev-preferred'], focus: 'engine features' });
  for (const focus of [question, action.focus]) {
    const html = renderToStaticMarkup(<ResponseBlocks blocks={[{ ...block, props: { records, question: focus } }]} />);
    const featured = html.slice(0, html.indexOf('class="comparison-models"'));
    for (const text of ['Engine &amp; fuel economy comparison', '6,500 rpm', '323 hp', '369',
      'Combined MPG · gasoline', '26', 'Combined MPGe · electric and gasoline', '56', '27', '17.8']) {
      assert.ok(featured.includes(text), text);
    }
    assert.equal((featured.match(/Combined system output/g) || []).length, 2);
    assert.ok(!html.includes('Comparison pricing'));
  }
});

test('specific comparison puts the requested metric above the vehicle cards', () => {
  const records = [
    { trim_id: 'first', name: '2.5 S', model: { name: 'CX-5' }, msrp_usd: '29990',
      specifications: [{ category: 'Performance', field: 'horsepower_87_aki', value: '187' }] },
    { trim_id: 'second', name: 'Preferred', model: { name: 'CX-90 PHEV', powertrain: 'plug_in_hybrid' },
      msrp_usd: '50695', specifications: [{ category: 'Performance', field: 'horsepower_91_aki', value: '323' }] },
  ];
  const html = renderToStaticMarkup(<ResponseBlocks blocks={[{
    type: 'ui', component: 'CarComparison', props: { records, question: 'Compare horsepower' },
  }]} />);
  const featured = html.slice(0, html.indexOf('class="comparison-models"'));
  assert.ok(featured.includes('Horsepower comparison') && featured.includes('187 hp') && featured.includes('323 hp'));
  assert.ok(featured.includes('91 AKI') && featured.includes('Combined system output'));
  assert.ok(!html.includes('Comparison pricing'));
});

test('explicit prior-year references are permitted only for the linked model and clearly labeled', () => {
  const asset = {asset_kind:'image',url:'https://example.com/reference.jpg',model_id:'',source_model_year:'2026',
    applicability:'model_reference',reference_model_id:'phev',product_trim_code:'prior-year-code',caption:'2026 PHEV reference; 2027 appearance and equipment may differ'};
  const record = {model_id:'phev',model_year:'2027',name:'PHEV',assets:[asset],trims:[{trim_id:'new',product_trim_code:'new-code'}]};
  assert.equal(components.vehiclePhotos(record).length,1);
  assert.equal(components.vehiclePhotos({...record,model_id:'other'}).length,0);
  const html = renderToStaticMarkup(<components.VehicleGallery records={[record]} />);
  assert.ok(html.includes('2026 reference') && html.includes('2027 appearance/equipment may differ'));
});

test('same-year trim-group photos omit boilerplate captions and keep descriptive alt text', () => {
  const asset = {asset_kind: 'image', url: 'https://example.com/vehicle.jpg',
    source_model_year: '2027', product_trim_code: 'trim',
    applicability_label: '2027 model / trim-group reference image'};
  const record = {model: {model_year: 2027, name: 'Mazda CX-5'}, photos: [asset]};
  const html = renderToStaticMarkup(<components.ComparisonPhoto record={record} showCaption />);
  assert.match(html, /alt="Mazda CX-5"/);
  assert.doesNotMatch(html, /trim-group reference|figcaption/);
});

test('prior-year gallery references follow their explicitly linked trim', () => {
  const record = {
    model_id: 'phev', model_year: '2027', name: 'CX-90 Plug-in Hybrid',
    trims: [{ trim_id: 'preferred', name: 'Preferred' }, { trim_id: 'sport', name: 'Sport' }],
    assets: ['preferred', 'sport'].map(trim => ({
      asset_kind: 'image', url: `https://example.com/${trim}.jpg`,
      applicability: 'model_reference', reference_model_id: 'phev',
      reference_trim_id: trim, source_model_year: '2026',
    })),
  };
  const html = renderToStaticMarkup(<components.VehicleVisualization records={[record]} />);
  assert.ok(html.includes('360° view is unavailable for this selection.'));
  assert.ok(html.includes('https://example.com/preferred.jpg'));
  assert.ok(!html.includes('https://example.com/sport.jpg'));
  assert.ok(!html.includes('Previous photo'));
  assert.ok(!html.includes('class="rotation-card"'));
});

import {CarList} from '../src/CarList.jsx';
test('model cards expose photos, distinct price and configuration highlights without a disabled selection wall', () => {
 const html = renderToStaticMarkup(<CarList startComparison cars={[{id:'a',name:'Mazda Mazda3',year:2027,msrp:28000,powertrain:'gasoline',image_url:'https://example.com/car.jpg',image_caption:'2027 model reference image; trim unspecified',configurations:[{trim_id:'x',name:'Select',msrp_usd:'28000',seating_capacity:'5',body_style:'Sedan',drivetrain:'AWD'}]}]} />);
 assert.ok(!html.includes('Mazda Mazda3'));
 assert.ok(html.includes('5 seats') && html.includes('Sedan') && html.includes('Starting MSRP'));
 assert.ok(html.includes('trim unspecified'));
 assert.ok(!html.includes('disabled=""'));
});


import {seatingSummary} from '../src/CarList.jsx';
test('seating summary splits choices, deduplicates and avoids invented intermediate seating', () => {
 assert.equal(seatingSummary(['8','5','7|8','7'].map(seating_capacity => ({seating_capacity}))), '5, 7 or 8 seats');
 assert.equal(seatingSummary(['5|6','7'].map(seating_capacity => ({seating_capacity}))), '5–7 seats');
});
test('image captions show applicability once without changing raw metadata', () => {
 const asset = {source_model_year:'2026',applicability:'model_reference',caption:'Long original'};
 assert.equal(components.comparisonCaption({model:{model_year:2027},image_is_reference:true},asset),'2026 reference · 2027 appearance/equipment may differ');
 assert.equal(components.comparisonCaption({model:{model_year:2027,name:'Mazda3'}},{source_model_year:'2027',applicability_label:'2027 model reference image; trim unspecified'}),'2027 Mazda3 · Trim not specified');
 assert.equal(asset.caption,'Long original');
});
test('explicit city highway pairs populate normalized overview and remain in raw details', () => {
 const html = renderToStaticMarkup(<components.CarComparison records={[{trim_id:'a',model:{name:'Model A'},specifications:[{category:'Efficiency',field:'AWD, AUTOMATIC TRANSMISSION (MPG, CITY/HWY)',value:'24 / 30'}]}]} />);
 assert.ok(html.includes('City MPG') && html.includes('Highway MPG'));
 assert.ok(html.includes('24 / 30'));
});


test('specification groups retain all fields and suppress only administrative applicability', () => {
 assert.equal(components.specificationNote('exact trim; retain value qualifiers including seating and charging conditions'), '');
 assert.equal(components.specificationNote('trim group. Verify seating-dependent values against exact configuration'), '');
 assert.equal(components.specificationNote('Two-seat third row only; premium 93 octane'), 'Two-seat third row only; premium 93 octane');
 for (const [field, expected] of [['horsepower_87_aki','Performance'],['charging_level_2_0_to_100_percent','Efficiency & charging'],['cargo_volume_sae_rows_upright_cubic_feet','Dimensions & space'],['wireless_phone_charging','Specifications']]) {
   assert.equal(components.specificationGroup({category:'specification',field}),expected);
 }
});

test('recommendations format long openings, model option markers and legacy bullets', () => {
  const intro = 'This is a long opening paragraph that should stay regular weight across several wrapped lines, even when it is the first assistant section in a reply.';
  const text = [intro, '', '- [option] CX-5 | Lower starting price.', '', 'Quick guidance by priority:', '- Budget: Look at CX-5.', '', 'Caveat: Inventory varies.'].join('\n');
  const html = renderToStaticMarkup(<ResponseBlocks blocks={[{type:'text', role:'answer', text}]} />);
  assert.ok(html.includes('class="response-body">' + intro));
  assert.ok(html.includes('class="micro-choice"><strong>CX-5</strong>'));
  assert.ok(html.includes('<ul class="micro-list"><li><strong>Budget:</strong>'));
  assert.ok(html.includes('class="micro-caution">Inventory varies.'));
  assert.ok(!html.includes('[option]'));
});

test('PHEV Preferred renders all seven sourced paint swatches', () => {
  const { records } = fixtures.find(fixture =>
    fixture.model === 'us-2027-cx90-phev' && fixture.component === 'ColorOptions');
  const record = records[0];
  const preferred = record.trims.find(trim => trim.name === 'PHEV Preferred');
  const colors = record.colors.filter(color => color.trim_id === preferred.trim_id);
  const html = renderToStaticMarkup(<components.ColorOptions records={[{ ...record, colors }]} />);
  assert.equal(colors.length, 7);
  const fills = [...html.matchAll(/background-color:#([a-f\d]{6})/gi)].map(match => match[1].toUpperCase());
  assert.deepEqual(fills, ['101312', '004291', '273754', 'FFFFFF', '4F535B', '890000', 'B2B0A1']);
  assert.ok(html.includes('Screen colors are approximate'));
});

test('CX-90 Turbo Select paint preview uses only the chosen exterior paint', () => {
  const { records } = fixtures.find(item =>
    item.model === 'us-2027-cx90-mhev' && item.component === 'VehicleDetails');
  const record = records[0];
  const trim = record.trims[0];
  const selected = { ...record, trims: [trim] };
  const color = record.colors.find(item => item.trim_id === trim.trim_id && item.color_code === '52M');
  const photos = components.colorPreviewPhotos(selected, color);
  assert.ok(photos.length > 0);
  assert.ok(photos.every(asset => asset.color_code === '52M' &&
    asset.product_trim_code === trim.product_trim_code));
  assert.equal(photos[0].source_field, 'bpTopLeftImage');
  const missing = record.colors.find(item => item.trim_id === trim.trim_id && item.color_code === '42M');
  const html = renderToStaticMarkup(<components.VehicleDetails records={[
    { ...selected, selected_color_id: missing.color_id },
  ]} />);
  assert.ok(html.includes('No matching exterior photo is available'));
  assert.ok(!html.includes('<img'));
  assert.ok(html.includes('Base MSRP'));
});

test('sourced paint previews match the selected PHEV trim and Mazda3 body style', () => {
  const { records: [phev] } = fixtures.find(item =>
    item.model === 'us-2027-cx90-phev' && item.component === 'VehicleDetails');
  const red = phev.colors.find(color => color.color_code === '46V' &&
    phev.trims.some(trim => trim.trim_id === color.trim_id && trim.name === 'PHEV Preferred'));
  const redPhotos = components.colorPreviewPhotos(phev, red);
  assert.equal(redPhotos.length, 1);
  assert.match(redPhotos[0].url, /Preferred-Soul-Red-front\.png$/);
  const html = renderToStaticMarkup(<components.VehicleDetails records={[
    { ...phev, selected_color_id: red.color_id },
  ]} />);
  assert.match(html, /2026 photo/);
  assert.match(html, /Soul Red Crystal Metallic exterior reference/);
  assert.doesNotMatch(html, /Listed for this trim|Swatch ·|<figcaption|appearance\/equipment may differ/);
  assert.match(html, /Features &amp; specs/);
  assert.match(html, /<dt>Paint surcharge<\/dt><dd>\$595\.00<\/dd>/);
  assert.match(html, /Change color/);
  assert.doesNotMatch(html, /color-options|View photos|View 360°/);

  const { records: [mazda3] } = fixtures.find(item =>
    item.model === 'us-2027-mazda3' && item.component === 'ColorOptions');
  const sedan = mazda3.trims.find(trim => trim.name === '2.5 S Select Sport' && trim.body_style === 'sedan');
  const ceramic = mazda3.colors.find(color => color.name === 'Ceramic Metallic');
  const sedanPhotos = components.colorPreviewPhotos({ ...mazda3, trims: [sedan] }, ceramic);
  assert.equal(sedanPhotos.length, 1);
  assert.match(sedanPhotos[0].url, /mazda3-sedan.*Ceramic-Metallic-front\.png$/);
  const quartz = mazda3.colors.find(color => color.name === 'Premium Quartz Metallic');
  assert.deepEqual(components.colorPreviewPhotos(mazda3, quartz), []);
});
