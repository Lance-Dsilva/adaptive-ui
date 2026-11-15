import { createContext, useContext } from 'react';

export const ReplyControlsDisabled = createContext(false);

export function ReplySummary({ children }) {
  const disabled = useContext(ReplyControlsDisabled);
  return <summary aria-disabled={disabled || undefined} tabIndex={disabled ? -1 : undefined}
    onClick={disabled ? event => event.preventDefault() : undefined}>
    {children}
  </summary>;
}
