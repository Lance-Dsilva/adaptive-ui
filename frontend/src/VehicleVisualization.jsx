import { ReplyControlsDisabled, ReplySummary } from './ReplyControls.jsx';
import { useContext, useEffect, useRef, useState } from 'react';
import './VehicleVisualization.css';
import { isHttpsUrl as https } from './isHttpsUrl.js';
export const safeFrameUrl = value => typeof value === 'string' && (https(value) || /^\/assets\/vehicle-rotations\/(?:[a-zA-Z0-9_-]+\/)*[a-zA-Z0-9_-]+\.(?:jpg|jpeg|png|webp)$/.test(value));
export const wrapFrame = (frame, count) => ((frame % count) + count) % count;
export const clampZoom = zoom => Math.min(2.5, Math.max(1, zoom));
export function verifiedSequences(record) {
  const codes = new Set((record.trims || []).map(trim => trim.product_trim_code).filter(Boolean));
  return (record.visualizations || []).flatMap(item => {
    if (item.status !== 'verified_frames' || item.model_id !== record.model_id || !item.product_trim_code || !codes.has(item.product_trim_code)) return [];
    try {
      const frames = JSON.parse(item.frame_urls_json || '[]');
      return Array.isArray(frames) && frames.length > 1 && frames.every(safeFrameUrl) && new Set(frames).size === frames.length ? [{...item, frames}] : [];
    } catch { return []; }
  });
}
function RotateIcon({ right = false }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={right ? {transform:'scaleX(-1)'} : undefined}><path d="M3 10a9 9 0 1 1 2 8"/><path d="M3 4v6h6"/></svg>;
}
function FrameViewer({ sequence, label }) {
  const disabled = useContext(ReplyControlsDisabled);
  const [frame, setFrame] = useState(0), [zoom, setZoom] = useState(1), [failed, setFailed] = useState(false);
  const pointers = useRef(new Map());
  useEffect(() => {
    // Warm the verified sequence locally so the first drag does not wait per angle.
    const images = sequence.frames.map(url => { const image = new Image(); image.src = url; return image; });
    return () => { for (const image of images) image.src = ''; };
  }, [sequence.frames]);
  const distance = () => { const [a,b] = [...pointers.current.values()]; return b ? Math.hypot(a.x-b.x,a.y-b.y) : 0; };
  const rotate = steps => setFrame(current => wrapFrame(current + steps, sequence.frames.length));
  const reset = () => { setFrame(0); setZoom(1); setFailed(false); pointers.current.clear(); };
  const release = event => pointers.current.delete(event.pointerId);
  const move = event => {
    if (disabled) return;
    const previous = pointers.current.get(event.pointerId);
    if (!previous || failed) return;
    if (pointers.current.size > 1) {
      const before = distance(); pointers.current.set(event.pointerId,{x:event.clientX,y:event.clientY});
      const after = distance(); if (before > 0) setZoom(current => clampZoom(current * after / before));
    } else {
      const steps = Math.trunc((event.clientX-previous.x)/12);
      if (steps) { rotate(-steps); pointers.current.set(event.pointerId,{x:previous.x+steps*12,y:event.clientY}); }
    }
  };
  return <>
    <div className="rotation-toolbar"><span className="rotation-view-label">{/interior/i.test(sequence.kind) ? 'Interior' : 'Exterior'}</span><button className="rotation-reset" type="button" onClick={reset}><RotateIcon />Reset</button></div>
    <div className="rotation-stage" tabIndex={disabled ? -1 : 0} role="group" aria-disabled={disabled || undefined}
      aria-label={disabled ? 'Vehicle preview' : 'Interactive vehicle rotation. Use left and right arrow keys to rotate.'}
      onPointerDown={event => { if (disabled || failed) return; event.currentTarget.setPointerCapture(event.pointerId); pointers.current.set(event.pointerId,{x:event.clientX,y:event.clientY}); }}
      onPointerMove={move} onPointerUp={release} onPointerCancel={release} onLostPointerCapture={release}
      onKeyDown={event => { if (disabled || failed) return; if (['ArrowLeft','ArrowRight'].includes(event.key)) { event.preventDefault(); rotate(event.key === 'ArrowLeft' ? -1 : 1); } if (event.key === 'Home') { event.preventDefault(); reset(); } }}>
      {failed ? <p role="status">This rotation image could not load. Try Reset or browse the photos below.</p> : <img src={sequence.frames[frame]} alt={`${label}, rotation frame ${frame+1} of ${sequence.frames.length}`} draggable={false} referrerPolicy="no-referrer" style={{transform:`scale(${zoom})`}} onError={() => setFailed(true)} />}
    </div>
    <div className="rotation-control-bar">
      <div className="rotation-control-group" role="group" aria-label="Rotation controls">
        <button type="button" disabled={failed} aria-label="Rotate left" onClick={() => rotate(-1)}><RotateIcon /></button>
        <button type="button" disabled={failed} aria-label="Rotate right" onClick={() => rotate(1)}><RotateIcon right /></button>
      </div>
      <div className="rotation-control-group" role="group" aria-label="Zoom controls">
        <button type="button" disabled={failed || zoom <= 1} aria-label="Zoom out" onClick={() => setZoom(current => clampZoom(current-.25))}>−</button>
        <span className="rotation-zoom" aria-label={`Zoom ${Math.round(zoom*100)} percent`}>{Math.round(zoom*100)}%</span>
        <button type="button" disabled={failed || zoom >= 2.5} aria-label="Zoom in" onClick={() => setZoom(current => clampZoom(current+.25))}>+</button>
      </div>
    </div>
    <div className="rotation-stage-footer">{!disabled && <span>Drag to rotate · Pinch to zoom</span>}<span role="status">{frame+1} / {sequence.frames.length}</span></div>
  </>;
}
export default function VehicleVisualizer({ record, fallback }) {
  const sequences = verifiedSequences(record);
  const [choice, setChoice] = useState('');
  const sequence = sequences.find(item => item.visualization_id === choice) || sequences[0];
  if (!sequence) return <>
    <p className="rotation-hint">360° view is unavailable for this selection.</p>
    {fallback}
  </>;
  const describe = item => {
    const trim = record.trims?.find(trim => trim.product_trim_code === item.product_trim_code);
    const color = record.colors?.find(color => color.color_code === item.color_code && color.product_trim_code === item.product_trim_code);
    return `${/interior/i.test(item.kind) ? 'Interior' : 'Exterior'} · ${trim?.name || 'Recorded configuration'}${color ? ` · ${color.name}` : ''}`;
  };
  return <section className="rotation-card"><h3>{record.name} · 360° view</h3>
      <p className="rotation-subtitle">{describe(sequence).replace(/^(Exterior|Interior) · /, '')}</p>
      {sequences.length > 1 && <label>View and color<select value={sequence.visualization_id} onChange={event => setChoice(event.target.value)}>{sequences.map(item => <option key={item.visualization_id} value={item.visualization_id}>{describe(item)}</option>)}</select></label>}
      
      <FrameViewer key={sequence.visualization_id} sequence={sequence} label={describe(sequence)} />
      <p className="rotation-preview-note">Representative preview · Equipment may differ.</p>
      <details className="rotation-info"><ReplySummary>Preview details & controls</ReplySummary>
        {sequence.caption && <p>{sequence.caption}</p>}
        <p>Drag horizontally or use the left and right arrow keys to rotate. Pinch or use the zoom buttons to enlarge. Reset or the Home key restores the starting view.</p>
      </details>
      <details><ReplySummary>Browse still photos</ReplySummary>{fallback}</details>
  </section>;
}
