import { authenticate, configureStoreSearch, defineMiddlewares } from "@medusajs/framework/http"
import { ensureCartOwner, ensureReturnOwner } from "./commerceops-ownership"

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
  ],
})
