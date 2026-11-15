import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import VehicleVisualizer, { verifiedSequences, wrapFrame, clampZoom, safeFrameUrl } from '../src/VehicleVisualization.jsx';
const record = {model_id:'model', name:'Fixture vehicle', trims:[{product_trim_code:'trim',name:'Preferred'}], colors:[{product_trim_code:'trim',color_code:'red',name:'Soul Red'}]};
const sequence = {visualization_id:'rotation', model_id:'model', product_trim_code:'trim',color_code:'red',kind:'exterior_image_sequence',status:'verified_frames',frame_urls_json:'["https://example.invalid/one.jpg","https://example.invalid/two.jpg"]',source_url:'https://example.invalid/source',checked_on:'2026-11-14'};
test('frame rotation wraps both ways and zoom remains bounded', () => {
  assert.equal(wrapFrame(-1,36),35); assert.equal(wrapFrame(36,36),0); assert.equal(wrapFrame(-73,36),35);
  assert.equal(clampZoom(.2),1); assert.equal(clampZoom(7),2.5); assert.equal(clampZoom(1.25),1.25);
});
test('verified viewer exposes actual color, accessible rotation and zoom without claiming mesh', () => {
  const input = {...record, visualizations:[sequence]}; const original = JSON.stringify(input);
  const html = renderToStaticMarkup(<VehicleVisualizer record={input} fallback={<p>Still photos</p>} />);
  for (const text of ['Soul Red','Preferred','Rotate left','Rotate right','Zoom in','Zoom out','Reset','360°', 'Exterior', 'preview']) assert.ok(html.includes(text));
  assert.ok(!html.includes('Interior'));
  assert.doesNotMatch(html, /Source|Checked 2026/);
  assert.equal(JSON.stringify(input),original);
});
test('unavailable manifests expose photo fallback without inert rotation controls', () => {
  const html = renderToStaticMarkup(<VehicleVisualizer record={{...record,visualizations:[{...sequence,status:'unresolved'}]}} fallback={<p>Still photos</p>} />);
  assert.ok(html.includes('unavailable')); assert.ok(html.includes('Still photos')); assert.ok(!html.includes('Rotate left'));
});
test('malformed, cross-trim, cross-model and insecure manifests never enable viewer', () => {
  for (const change of [{model_id:'other'},{product_trim_code:'other'},{frame_urls_json:'oops'},{frame_urls_json:'["http://bad/a","http://bad/b"]'},{frame_urls_json:'["https://example.invalid/a","https://example.invalid/a"]'}]) assert.deepEqual(verifiedSequences({...record,visualizations:[{...sequence,...change}]}),[]);
});

test('cached rotation frame URLs allow only the explicit local asset namespace', () => {
  assert.ok(safeFrameUrl('/assets/vehicle-rotations/cx5-51k/frame-001.jpg'));
  for (const url of ['/assets/other/frame.jpg','/assets/vehicle-rotations/../secret.jpg','/assets/vehicle-rotations/a%2fb.jpg','//evil.test/assets/vehicle-rotations/a.jpg','/assets/vehicle-rotations/a.jpg?redirect=x','/assets/vehicle-rotations/a.svg','javascript:alert(1)']) assert.equal(safeFrameUrl(url),false);
});
