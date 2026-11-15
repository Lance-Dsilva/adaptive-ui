import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ResponseBlocks, previousTurnsFor, responseText } from './ResponseBlocks.jsx';
import { TestDriveRequest } from './TestDriveRequest.jsx';
import './styles.css';

const DISCOVER = 'Show me Mazda SUVs.';
const COMPARE = 'Can you show me what cars are available for 2027?';
const CHAT_ERRORS = {
  timeout: 'The assistant took too long to respond. Try again.',
  busy: 'The assistant is busy. Try again in a moment.',
  selection: 'That request couldn’t be accepted. Try asking again in the chat box.',
  connection: 'Couldn’t reach the assistant. Check your connection and try again.',
  service: 'The assistant couldn’t complete this request. Try again.',
};

function Icon({ name, ...props }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" {...props}>
      {name === 'spark' && <path fill="currentColor" d="M10.6 2c.35-1.3 2.45-1.3 2.8 0 1.4 5.2 3.4 7.2 8.6 8.6 1.3.35 1.3 2.45 0 2.8-5.2 1.4-7.2 3.4-8.6 8.6-.35 1.3-2.45 1.3-2.8 0-1.4-5.2-3.4-7.2-8.6-8.6-1.3-.35-1.3-2.45 0-2.8C7.2 9.2 9.2 7.2 10.6 2Z" />}
      {name === 'send' && <path fill="currentColor" d="m3 10 17-7c.8-.3 1.5.4 1.3 1.2l-4.4 16.1c-.2.7-1 .9-1.6.4l-4.8-4.1-2.4 2.5v-4.7L17 7.5l-10.5 5.7-3.6-1.6c-.7-.3-.6-1.3.1-1.6Z" />}
      {name === 'more' && [5, 12, 19].map(y => <circle key={y} cx="12" cy={y} r="1.8" fill="currentColor" />)}
    </svg>
  );
}

function App() {
  const [aiConfigured, setAiConfigured] = useState(false);
  const [testDriveEnabled, setTestDriveEnabled] = useState(false);
  const [showTestDrive, setShowTestDrive] = useState(false);
  const [requestPending, setRequestPending] = useState(false);
  const [draft, setDraft] = useState('');
  const [turns, setTurns] = useState([]);
  const [pending, setPending] = useState(false);
  const [menu, setMenu] = useState(false);
  const nextId = useRef(0);
  const activeRequest = useRef(null);
  const log = useRef(null);
  const latest = useRef(null);
  const input = useRef(null);
  const welcome = turns.length === 0;

  useEffect(() => {
    if (!latest.current || !log.current) return;
    log.current.scrollTop = latest.current.offsetTop - log.current.offsetTop;
  }, [turns, pending]);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/capabilities', { signal: controller.signal }).then(response => response.json())
      .then(data => {
        setAiConfigured(data.ai_configured === true);
        setTestDriveEnabled(data.test_drive_enabled === true);
      }).catch(() => {});
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const handler = event => {
      const action = event.detail;
      if (typeof action?.message === 'string') {
        send(action.message, action.compare === true, null, action.vehicleAction);
      }
    };
    window.addEventListener('shopping-prompt', handler);
    return () => window.removeEventListener('shopping-prompt', handler);
  });

  useEffect(() => () => activeRequest.current?.abort(), []);

  async function send(message, compare = false, retryId = null, action = null, contextTurnId = null) {
    const text = message.trim();
    if (!text || activeRequest.current || requestPending) return;
    const id = retryId ?? nextId.current++;
    const controller = new AbortController();
    activeRequest.current = controller;
    const previous = previousTurnsFor(turns, id, contextTurnId);
    const history = previous.map(turn => turn.message);
    const transcript = previous.flatMap(turn => [
      { role: 'user', content: turn.message },
      { role: 'assistant', content: responseText(turn.blocks) },
    ]).slice(-40);
    const timeout = setTimeout(() => controller.abort(), 120000);
    const update = changes => setTurns(current =>
      current.map(turn => turn.id === id ? { ...turn, ...changes } : turn)
    );
    if (retryId === null) {
      setTurns(current => [...current, { id, message: text, compare, action, contextTurnId }]);
      setDraft('');
    } else {
      update({ error: false });
    }
    setPending(true);
    setShowTestDrive(false);
    let receivedResponse = false;
    try {
      const response = await fetch('/chat', {
        method: 'POST',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history, transcript, vehicle_action: action }),
        signal: controller.signal,
      });
      receivedResponse = true;
      if (!response.ok) {
        const error = { 408: 'timeout', 504: 'timeout', 429: 'busy', 422: 'selection' }[response.status];
        update({ error: error ?? 'service' });
        return;
      }
      const { blocks } = await response.json();
      if (!Array.isArray(blocks) || blocks.length === 0) throw new Error('Missing chat blocks');
      update({ blocks });
    } catch (error) {
      if (error.name === 'AbortError') update({ error: 'timeout' });
      else update({ error: receivedResponse ? 'service' : 'connection' });
    } finally {
      clearTimeout(timeout);
      activeRequest.current = null;
      setPending(false);
    }
  }

  return (
    <div className="shell">
      <header className="header">
        <img src="/assets/mazda-mark.webp" className="brand-mark" alt="" />
        <div className="brand">
          <strong>Austin Mazda</strong>
          <span><i />{aiConfigured ? 'AI assistant' : '2027 Mazda research'}</span>
        </div>
        <div className="menu">
          <button className="icon-button" type="button" aria-label="Chat options" aria-expanded={menu}
            onClick={() => setMenu(!menu)}><Icon name="more" /></button>
          {menu && <div className="menu-popover">
            <button type="button" disabled={pending || requestPending} onClick={() => {
              setTurns([]);
              setShowTestDrive(false);
              setDraft('');
              setMenu(false);
              input.current?.focus();
            }}>New chat</button>
            {testDriveEnabled && <button type="button" disabled={pending || requestPending} onClick={() => {
              setShowTestDrive(true); setMenu(false);
            }}>Request test drive</button>}
          </div>}
        </div>
      </header>

      <main className={welcome && !showTestDrive ? 'main welcome' : 'main conversation'} ref={log}
        aria-label={showTestDrive ? 'Test-drive request' : welcome ? 'Welcome' : 'Conversation'}>
        <div className="test-drive-panel" hidden={!showTestDrive}>
          <button className="back-to-chat" type="button" disabled={requestPending} onClick={() => {
            setShowTestDrive(false);
            input.current?.focus();
          }}>Back to chat</button>
          <TestDriveRequest active={showTestDrive} onPendingChange={setRequestPending} />
        </div>
        {!showTestDrive && (welcome ? (
          <section className="hero">
            <Icon name="spark" className="spark" />
            <h1>Find your<br />next Mazda.</h1>
            <p>Explore models, trims, and starting prices.</p>
            <div className="suggestions">
              <button type="button" onClick={() => send(DISCOVER)}>Explore SUVs <span className="chevron" /></button>
              <button type="button" onClick={() => send(COMPARE, true)}>Compare models <span className="chevron" /></button>
            </div>
          </section>
        ) : turns.map((turn, index) => (
          <article className="turn" key={turn.id} ref={index === turns.length - 1 ? latest : undefined}>
            <p className="user-message">{turn.message}</p>
            <div className="reply" aria-live="polite" aria-busy={!turn.blocks && !turn.error}>
              <Icon name="spark" className="spark" />
              {turn.blocks ? <ResponseBlocks blocks={turn.blocks} compare={turn.compare}
                disabled={index !== turns.length - 1 || pending || requestPending}
                onAction={action => send(action.message, action.compare === true, null, action.vehicle_action ?? null, turn.id)} /> : turn.error ? (
                <div className="chat-error">
                  <p>{CHAT_ERRORS[turn.error]}</p>
                  <button type="button" disabled={index !== turns.length - 1 || pending || requestPending}
                    onClick={() => send(turn.message, turn.compare, turn.id, turn.action, turn.contextTurnId ?? null)}>Try again</button>
                </div>
              ) : <p role="status">Working on your request…</p>}
            </div>
          </article>
        )))}
      </main>

      <footer className="footer">
        {welcome && <p className="signup-note">No sign-up needed</p>}
        <form className="composer" onSubmit={event => {
          event.preventDefault();
          send(draft);
        }}>
          <input disabled={requestPending} aria-label="Message" placeholder={aiConfigured ? 'Ask about your next Mazda…' : 'Ask about 2027 Mazda models…'} value={draft} maxLength={2000}
            ref={input} onChange={event => setDraft(event.target.value)} />
          <button className="send icon-button" type="submit" aria-label="Send message"
            disabled={!draft.trim() || pending || requestPending}><Icon name="send" /></button>
        </form>
      </footer>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
