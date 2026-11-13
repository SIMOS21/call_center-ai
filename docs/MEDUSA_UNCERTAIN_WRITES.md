# Reconciliation of uncertain Medusa writes

Cart preparation and updates use several Medusa writes. Creation, line additions, quantity changes and removals are not one transaction. The gateway reads after each write and checks the complete expected variant/quantity map. After a lost reply, it attempts read-only reconciliation once. It never repeats that write. If the result remains uncertain or a subsequent line fails, CommerceOps returns `needs_review`, consumes the approval and stops the remaining changes. A known cart stays linked to its authenticated customer for read-only inspection.

## Required handling

1. Do not retry the confirmation, create another cart, complete checkout, or treat the action as successful.
2. Ask the customer to inspect the linked cart through the read-only cart view. If it is unavailable or incomplete, route the case to an authorized store operator.
3. The operator verifies the customer and cart in Medusa using read-only access first, and compares the cart lines with the approved product, variant, quantity, price, and currency. Do not use another customer's session or credentials.
4. Compare every approved operation and every pre-existing line, not just the last selected product. If the whole cart matches the approved target, report only the confirmed cart state. Checkout and payment have not been performed.
5. If the cart is absent, partial, or cannot be verified, keep the case unresolved and obtain an explicit customer decision before any manual store action. Do not silently delete, complete, refund, or duplicate the cart.
6. Only after the operator has established the actual state and the customer confirms the next action may a new preparation be authorized. Preserve the original `needs_review` audit record.

## Persistent locks and interrupted processes

The additive SQLite table `cart_action_locks` reserves an existing cart for one approval. A claim is committed before the catalogue/cart revalidation and business writes. A `confirmed` approval interrupted by process termination and a `needs_review` approval retain their lock. Read-only inspection remains possible; other sessions cannot prepare changes or checkout for that cart. Terminal completed, cancelled, invalidated or definitively failed actions release the lock. A newly created cart with an uncertain outcome is locked as soon as its identity is known.

There is deliberately no automatic timeout that unlocks an uncertain business operation. An authorized operator must stop competing activity, verify the actual Medusa cart and the original approval, preserve an audit record of reconciliation and decide whether the lock can be released. No customer-facing unlock endpoint is supplied. Do not delete a lock merely because it is old. If no cart identity was returned, retain the unresolved approval and escalate to the merchant before creating another cart.

Existing JSON states are upgraded additively to schema version 2 when read. Completed carts remain readable. Pending approvals created before option labels were included in the commercial snapshot are invalidated on confirmation and require a fresh approval. This avoids treating an old incomplete snapshot as authorization for new commercial characteristics.

This procedure addresses the uncertain outcome without compensation writes or automatic retries. It does not provide atomicity across Medusa's cart and line-item endpoints; unresolved cases still require operator review.
