import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { billingApi } from './studio';

// The price list (credits per action) comes from the server once and is shared by every
// button that shows a cost. Nothing is shown outside the paid edition.
let cache = null;

export function useCosts() {
  const { usage } = useAuth();
  const paid = !!usage?.paid;
  const [costs, setCosts] = useState(cache);
  useEffect(() => {
    if (!paid || cache) return undefined;
    let live = true;
    billingApi.plans()
      .then((c) => { cache = c.costs; if (live) setCosts(c.costs); })
      .catch(() => {});
    return () => { live = false; };
  }, [paid]);
  return paid ? costs : null;
}
