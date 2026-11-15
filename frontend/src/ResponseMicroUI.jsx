import { ReplySummary } from './ReplyControls.jsx';
export const microUI = Object.freeze({
  lead: ({ text }) => <p className="response-answer"><Inline text={text} /></p>,
  paragraph: ({ text }) => <p className="response-body"><Inline text={text} /></p>,
  heading: ({ text }) => <h3 className="micro-heading"><Inline text={text} /></h3>,
  bullets: ({ items }) => <ul className="micro-list">{listItems(items)}</ul>,
  steps: ({ items }) => <ol className="micro-list">{listItems(items)}</ol>,
  strong: ({ text }) => <strong>{text}</strong>,
  emphasis: ({ text }) => <em>{text}</em>,
  highlight: ({ text }) => <mark className="micro-highlight">{text}</mark>,
  code: ({ text }) => <code className="micro-code">{text}</code>,
  labelValue: ({ title, text }) => <dl className="micro-fact"><dt>{title}</dt><dd><Inline text={text} /></dd></dl>,
  metric: ({ title, text }) => <dl className="micro-fact micro-metric"><dt>{title}</dt><dd><Inline text={text} /></dd></dl>,
  choice: ({ title, text }) => <div className="micro-choice"><strong>{title}</strong><p><Inline text={text} /></p></div>,
  callout: ({ text }) => <p className="micro-callout"><Inline text={text} /></p>,
  caution: ({ text }) => <p className="micro-caution"><Inline text={text} /></p>,
  quote: ({ text }) => <blockquote className="micro-quote"><Inline text={text} /></blockquote>,
  divider: () => <hr className="micro-divider" />,
  disclosure: ({ title, text }) => <details className="response-disclosure"><ReplySummary>{title}</ReplySummary><p><Inline text={text} /></p></details>,
  question: ({ text }) => <p className="micro-question"><Inline text={text} /></p>,
  checklist: ({ items }) => <ul className="micro-list">{listItems(items, true)}</ul>,
});

function listItems(items, checks = false) {
  return items.map((item, index) => <li key={index}>
    {checks && <strong>{item.checked ? 'Done: ' : 'To do: '}</strong>}
    <Inline text={checks ? item.text : item} />
  </li>);
}

const inlineTokens = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|==[^=\n]+==|`[^`\n]+`)/g;

export function Inline({ text }) {
  return text.split(inlineTokens).map((part, index) => {
    if (index % 2 === 0) return part;
    const prefix = part.startsWith('**') ? '**' : part.startsWith('==') ? '==' : part[0];
    const Render = microUI[{'**': 'strong', '*': 'emphasis', '==': 'highlight', '`': 'code'}[prefix]];
    return <Render key={index} text={part.slice(prefix.length, -prefix.length)} />;
  });
}

// Convert a small, text-only syntax. React escapes all content, including HTML.
export function parseReplyText(text, role = 'body') {
  const blocks = [];
  function append(kind, item) {
    const last = blocks.at(-1);
    if (last?.kind === kind && last.items) last.items.push(item);
    else blocks.push({ kind, items: [item] });
  }
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim().replace(/^(?:[-*•]\s+)?\[option\]\s+/i, '[choice] ');
    if (/^(?:(?:[-*•]|\d+[.)])\s+)?\[source\](?:\s|$)/i.test(line)) continue;
    if (!line) {
      if (blocks.at(-1)?.kind !== 'gap') blocks.push({ kind: 'gap' });
      continue;
    }
    let match;
    if ((match = /^(?:Caveat|Note|Important):\s*(.+)$/i.exec(line))) {
      blocks.push({ kind: /^important/i.test(line) ? 'callout' : 'caution', text: match[1] });
    } else if ((match = /^#{1,4}\s+(.+)$/.exec(line))) {
      blocks.push({ kind: 'heading', text: match[1] });
    } else if (/^[A-Za-z][A-Za-z &-]{1,43}:$/.test(line)) {
      blocks.push({ kind: 'heading', text: line.slice(0, -1) });
    } else if (/^---$/.test(line)) {
      blocks.push({ kind: 'divider' });
    } else if ((match = /^>\s+(.+)$/.exec(line))) {
      blocks.push({ kind: 'quote', text: match[1] });
    } else if ((match = /^[-*]\s+\[([ xX])\]\s+(.+)$/.exec(line))) {
      append('checklist', { checked: match[1] !== ' ', text: match[2] });
    } else if ((match = /^[-*•]\s+(.+)$/.exec(line))) {
      append('bullets', match[1].replace(/^([^:*]{1,45}):\s+/, '**$1:** '));
    } else if ((match = /^\d+[.)]\s+(.+)$/.exec(line))) {
      append('steps', match[1]);
    } else if ((match = /^\[(lead|question|choice|fact|metric|details)\]\s+(.+)$/.exec(line))) {
      const [, tag, value] = match;
      const pair = /^([^|]+)\|(.+)$/.exec(value);
      const kind = { fact: 'labelValue', details: 'disclosure' }[tag] || tag;
      if (tag === 'lead' || tag === 'question') blocks.push({ kind, text: value });
      else if (pair) {
        blocks.push({ kind, title: pair[1].trim(), text: pair[2].trim() });
      } else blocks.push({ kind: 'paragraph', text: line });
    } else if (blocks.at(-1)?.kind === 'paragraph') {
      blocks.at(-1).text += ' ' + line;
    } else {
      blocks.push({ kind: 'paragraph', text: line });
    }
  }
  const visible = blocks.filter(block => block.kind !== 'gap');
  const first = visible[0];
  if (first && role === 'answer' && first.kind === 'paragraph' &&
      first.text.length <= 140 && first.text.split(/\s+/).length <= 22) first.kind = 'lead';
  return visible;
}

export function ReplyText({ text, role }) {
  if (role === 'notice' || role === 'status') return <p className={`response-${role}`}
    role={role === 'status' ? 'status' : undefined}><Inline text={text} /></p>;
  const parsed = parseReplyText(text, role);
  return <div className="micro-reply">
    {parsed.map(({ kind, ...props }, index) => {
      const Render = microUI[kind];
      return <Render key={index} {...props} />;
    })}
  </div>;
}
