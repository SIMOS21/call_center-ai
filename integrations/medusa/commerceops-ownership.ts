import { AuthenticatedMedusaRequest, MedusaResponse, MedusaNextFunction } from "@medusajs/framework/http"
import { ContainerRegistrationKeys } from "@medusajs/framework/utils"

export async function ensureReturnOwner(req: AuthenticatedMedusaRequest, res: MedusaResponse, next: MedusaNextFunction) {
  const body = req.body as { order_id?: string; receive_now?: boolean }
  if (!body?.order_id || body.receive_now) {
    res.status(400).json({ message: "Order required; receive_now is forbidden" })
    return
  }
  const query = req.scope.resolve(ContainerRegistrationKeys.QUERY)
  const { data: [order] } = await query.graph({ entity: "order", fields: ["id", "customer_id"], filters: { id: body.order_id } })
  if (!order || order.customer_id !== req.auth_context.actor_id) {
    res.status(403).json({ message: "Order access denied" })
    return
  }
  if (process.env.COMMERCEOPS_RETURNS_ENABLED !== "true") {
    res.status(403).json({ message: "Returns require merchant enablement; no financial refund" })
    return
  }
  next()
}

export async function ensureCartOwner(req: AuthenticatedMedusaRequest, res: MedusaResponse, next: MedusaNextFunction) {
  const query = req.scope.resolve(ContainerRegistrationKeys.QUERY)
  const { data: [cart] } = await query.graph({ entity: "cart", fields: ["id", "customer_id"], filters: { id: req.params.id } })
  if (!cart || cart.customer_id !== req.auth_context.actor_id) {
    res.status(403).json({ message: "Cart access denied" })
    return
  }
  next()
}

