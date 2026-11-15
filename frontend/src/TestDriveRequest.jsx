import { useEffect, useRef, useState } from 'react';

const EMPTY_FIELDS = { model_id: '', requested_date: '', requested_time: '' };

export function TestDriveRequest({ active = true, onPendingChange }) {
  const [models, setModels] = useState([]);
  const [fields, setFields] = useState(EMPTY_FIELDS);
  const [phase, setPhase] = useState('edit');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const heading = useRef(null);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    onPendingChange?.(phase === 'sending');
  }, [phase, onPendingChange]);
  useEffect(() => {
    if (active) heading.current?.focus();
  }, [active, phase]);
  const sending = useRef(false);
  useEffect(() => {
    if (!active) return;
    setLoading(true);
    setError('');
    const controller = new AbortController();
    fetch('/catalog/models', { signal: controller.signal }).then(response => {
      if (!response.ok) throw new Error();
      return response.json();
    }).then(data => {
      setModels(data);
      setLoading(false);
    }).catch(error => {
      if (error.name !== 'AbortError') {
        setError('Vehicle choices could not be loaded. Try loading them again.');
        setLoading(false);
      }
    });
    return () => controller.abort();
  }, [active, reload]);
  const model = models.find(item => item.id === fields.model_id);
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Chicago' }).format(new Date());

  async function submit() {
    if (sending.current) return;
    sending.current = true;
    setPhase('sending');
    setError('');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch('/test-drive-requests', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fields), signal: controller.signal,
      });
      if (response.status === 422) {
        const failure = await response.json();
        setError(typeof failure.detail === 'string' ? failure.detail : 'Please check your request details.');
        setPhase('edit');
        return;
      }
      if (!response.ok) throw new Error();
      const result = await response.json();
      if (result.status !== 'demo_accepted') throw new Error();
      setFields(EMPTY_FIELDS);
      setPhase('complete');
    } catch {
      setError('The demo couldn’t finish. Try again.');
      setPhase('review');
    } finally {
      clearTimeout(timer);
      sending.current = false;
    }
  }

  if (phase === 'complete') return <section className="experience-card" role="status">
    <h3 tabIndex="-1" ref={heading}>Test-drive demo complete</h3>
    <p>No details were saved and no appointment was booked.</p>
    <button type="button" onClick={() => setPhase('edit')}>Try another test drive</button>
  </section>;

  return <section className="experience-card">
    <h3 tabIndex="-1" ref={heading}>{phase === 'edit' ? 'Test drive' : 'Review your test drive'}</h3>
    <p>Choose a preferred date and time in America/Chicago. This demo does not save details or book a visit.</p>
    {error && <p role="alert">{error}</p>}
    <p role="status" aria-live="polite">{phase === 'sending' ? 'Checking your selection…' : ''}</p>
    {phase === 'edit' && !loading && models.length === 0 && <button type="button" onClick={() => setReload(value => value + 1)}>Reload vehicle choices</button>}
    {phase === 'edit' ? <form className="request-fields" onSubmit={event => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const next = Object.fromEntries(Object.keys(fields).map(field => [field, String(form.get(field) || '').trim()]));
      if (Object.values(next).some(value => !value)) {
        setError('Complete every field before reviewing your request.');
        return;
      }
      setFields(next);
      setError('');
      setPhase('review');
    }}>
      <label>Vehicle<select name="model_id" required value={fields.model_id} disabled={loading}
        onChange={event => setFields(current => ({ ...current, model_id: event.target.value }))}>
        <option value="">{loading ? 'Loading models…' : 'Choose a model'}</option>
        {models.map(item => <option key={item.id} value={item.id}>{item.year} {item.name}</option>)}
      </select></label>
      {[['requested_date', 'Preferred date', 'date'], ['requested_time', 'Preferred time', 'time']].map(([field, label, type]) =>
        <label key={field}>{label}<input name={field} required type={type} value={fields[field]}
          min={type === 'date' ? today : undefined}
          onChange={event => setFields(current => ({ ...current, [field]: event.target.value }))} /></label>)}
      <button type="submit" disabled={loading || !models.length}>Review request</button>
    </form> : <>
      <dl><div><dt>Vehicle</dt><dd>{model?.name}</dd></div>
        <div><dt>Preferred time</dt><dd>{fields.requested_date} at {fields.requested_time}</dd></div></dl>
      <div className="experience-actions">
        <button type="button" disabled={phase === 'sending'} onClick={submit}>
          {phase === 'sending' ? 'Checking…' : 'Accept test-drive demo'}
        </button>
        {phase === 'review' && <button type="button" onClick={() => setPhase('edit')}>Edit details</button>}
      </div>
    </>}
  </section>;
}
