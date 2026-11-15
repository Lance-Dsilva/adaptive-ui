import { useState } from 'react';

const calendarLabel = new Intl.DateTimeFormat('en-US', {
  month: 'long', year: 'numeric', timeZone: 'UTC',
});
const dayLabel = new Intl.DateTimeFormat('en-US', { dateStyle: 'full', timeZone: 'UTC' });
const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function Calendar({ firstDate, lastDate, selected, onSelect }) {
  const [month, setMonth] = useState(firstDate.slice(0, 7));
  const [year, number] = month.split('-').map(Number);
  const start = new Date(Date.UTC(year, number - 1, 1));
  const dayCount = new Date(Date.UTC(year, number, 0)).getUTCDate();

  function move(offset) {
    setMonth(new Date(Date.UTC(year, number - 1 + offset, 1)).toISOString().slice(0, 7));
  }

  return <div className="test-drive-calendar">
    <div className="test-drive-calendar-header">
      <button type="button" aria-label="Previous month" disabled={month <= firstDate.slice(0, 7)}
        onClick={() => move(-1)}>‹</button>
      <strong aria-live="polite">{calendarLabel.format(start)}</strong>
      <button type="button" aria-label="Next month" disabled={month >= lastDate.slice(0, 7)}
        onClick={() => move(1)}>›</button>
    </div>
    <div role="group" aria-label="Preferred date" className="test-drive-calendar-days">
      {weekdays.map(day => <span key={day} aria-hidden="true">{day}</span>)}
      {Array.from({ length: start.getUTCDay() }, (_, index) => <span key={index} aria-hidden="true" />)}
      {Array.from({ length: dayCount }, (_, index) => {
        const day = index + 1;
        const date = new Date(Date.UTC(year, number - 1, day));
        const value = date.toISOString().slice(0, 10);
        return <button key={value} type="button" disabled={value < firstDate || value > lastDate}
          aria-label={dayLabel.format(date)} aria-pressed={selected === value}
          onClick={() => onSelect(value)}>{day}</button>;
      })}
    </div>
  </div>;
}

export function TestDriveRequest({ records }) {
  const { models, first_date: firstDate, last_date: lastDate } = records[0];
  const [model, setModel] = useState('');
  const [date, setDate] = useState('');
  const [pending, setPending] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    const time = new FormData(event.currentTarget).get('requested_time');
    if (pending || !model || !date || !time) return;
    setPending(true);
    setError('');
    try {
      const response = await fetch('/test-drive-requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: model, requested_date: date, requested_time: time }),
        signal: AbortSignal.timeout(30000),
      });
      const result = await response.json();
      if (!response.ok || result.status !== 'demo_accepted') {
        setError(typeof result.detail === 'string' ? result.detail : 'Check your selections and try again.');
        return;
      }
      setModel('');
      setDate('');
      setAccepted(true);
    } catch {
      setError('Unable to check your selections. Try again.');
    } finally {
      setPending(false);
    }
  }

  if (accepted) return <section className="experience-card" role="status">
    <h3>Test-drive demo complete</h3>
    <p>Your selections were cleared. To book a visit, contact the dealership.</p>
  </section>;

  return <section className="experience-card test-drive-card">
    <h3>Test drive</h3>
    <p className="experience-note">Demo only. Your selections aren’t saved and no appointment is booked.</p>
    <form className="request-fields" onSubmit={submit}>
      <label>Vehicle<select required value={model} onChange={event => setModel(event.target.value)}>
        <option value="">Choose a model</option>
        {models.map(item => <option key={item.id} value={item.id}>{item.year} {item.name}</option>)}
      </select></label>
      <Calendar firstDate={firstDate} lastDate={lastDate} selected={date} onSelect={setDate} />
      <label>Preferred time (Central)<input name="requested_time" required type="time" /></label>
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={pending || !model || !date}>
        {pending ? 'Checking…' : 'Submit preference'}
      </button>
    </form>
  </section>;
}
