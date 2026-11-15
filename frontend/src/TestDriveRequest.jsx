import { useEffect, useRef, useState } from 'react';

export function TestDriveRequest({ active = true, onPendingChange }) {
  const [models, setModels] = useState([]);
  const [fields, setFields] = useState({ model_id: '', requested_date: '', requested_time: '', name: '', email: '' });
  const [phase, setPhase] = useState('edit');
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const heading = useRef(null);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    onPendingChange?.(phase === 'sending' || phase === 'retry');
  }, [phase, onPendingChange]);
  useEffect(() => {
    if (active) heading.current?.focus();
  }, [active, phase]);
  const key = useRef(crypto.randomUUID());
  const sending = useRef(false);
  useEffect(() => {
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
  }, [reload]);
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
        body: JSON.stringify({ ...fields, idempotency_key: key.current }), signal: controller.signal,
      });
      if (response.status === 422) {
        const failure = await response.json();
        setError(typeof failure.detail === 'string' ? failure.detail : 'Please check your request details.');
        setPhase('edit');
        return;
      }
      if (!response.ok) throw new Error();
      setResult(await response.json());
      setPhase('complete');
    } catch {
      setError('The request could not be confirmed. Retry to check and save the same request.');
      setPhase('retry');
    } finally {
      clearTimeout(timer);
      sending.current = false;
    }
  }

  if (result) return <section className="experience-card" role="status">
    <h3 tabIndex="-1" ref={heading}>Test-drive preference saved locally</h3>
    <p>{model?.name} · {result.requested_date} at {result.requested_time}</p>
    <p>{result.timezone} · Local request</p>
    <p>Reference {result.request_id}</p>
    <p className="experience-note">Your preferred time and contact details are recorded on this computer. Contact the dealership to arrange and confirm the appointment; this app has no dealership notification connection.</p>
  </section>;

  return <section className="experience-card">
    <h3 tabIndex="-1" ref={heading}>{phase === 'review' ? 'Review your request' : 'Save a test-drive request'}</h3>
    <p>Choose a preferred date and time in America/Chicago. This form saves a local request. Contact the dealership separately to confirm availability and arrange the visit.</p>
    {error && <p role="alert">{error}</p>}
    <p role="status" aria-live="polite">{phase === 'sending' ? 'Saving your local request…' : phase === 'retry' ? 'Save status is uncertain. Retry the same request to resolve it.' : ''}</p>
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
      {[['requested_date', 'Preferred date', 'date'], ['requested_time', 'Preferred time', 'time'],
        ['name', 'Your name', 'text'], ['email', 'Email address', 'email']].map(([field, label, type]) =>
        <label key={field}>{label}<input name={field} required type={type} value={fields[field]}
          min={type === 'date' ? today : undefined} maxLength={field === 'name' ? 100 : field === 'email' ? 254 : undefined}
          autoComplete={field === 'name' ? 'name' : field === 'email' ? 'email' : undefined}
          onChange={event => setFields(current => ({ ...current, [field]: event.target.value }))} /></label>)}
      <p className="experience-note">Your name, email, vehicle, and preferred time will be saved locally for this request.</p>
      <button type="submit" disabled={loading || !models.length}>Review request</button>
    </form> : <>
      <dl><div><dt>Vehicle</dt><dd>{model?.name}</dd></div>
        <div><dt>Preferred time</dt><dd>{fields.requested_date} at {fields.requested_time}</dd></div>
        <div><dt>Name</dt><dd>{fields.name}</dd></div><div><dt>Email</dt><dd>{fields.email}</dd></div></dl>
      <div className="experience-actions">
        <button type="button" disabled={phase === 'sending'} onClick={submit}>
          {phase === 'sending' ? 'Saving request…' : phase === 'retry' ? 'Retry same request' : 'Save local request'}
        </button>
        {phase === 'review' && <button type="button" onClick={() => setPhase('edit')}>Edit details</button>}
      </div>
    </>}
  </section>;
}
