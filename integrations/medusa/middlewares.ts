import { authenticate, configureStoreSearch, defineMiddlewares } from "@medusajs/framework/http"
import { ensureCartOwner, ensureCustomerCartOwner, ensureReturnOwner } from "./commerceops-ownership"

export default defineMiddlewares({
  routes: [
    {
      method: ["POST"],
      matcher: "/store/search",
      middlewares: [configureStoreSearch({ allowed_indexes: { product: true } })],
    },
    {
      method: ["POST"],
      matcher: "/store/returns",
      middlewares: [authenticate("customer", ["session", "bearer"]), ensureReturnOwner],
    },
    {
      method: ["POST"],
      matcher: "/store/carts/:id/complete",
      middlewares: [authenticate("customer", ["session", "bearer"]), ensureCartOwner],
    },
    {
      method: ["GET", "POST"],
      matcher: "/store/carts/:id",
      middlewares: [authenticate("customer", ["session", "bearer"], { allowUnauthenticated: true, requireMfa: true }), ensureCustomerCartOwner],
    },
    {
      method: ["POST"],
      matcher: "/store/carts/:id/line-items",
      middlewares: [authenticate("customer", ["session", "bearer"], { allowUnauthenticated: true, requireMfa: true }), ensureCustomerCartOwner],
    },
    {
      method: ["POST", "DELETE"],
      matcher: "/store/carts/:id/line-items/:line_id",
      middlewares: [authenticate("customer", ["session", "bearer"], { allowUnauthenticated: true, requireMfa: true }), ensureCustomerCartOwner],
    },
  ],
})
