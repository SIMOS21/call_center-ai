import { ExecArgs } from "@medusajs/framework/types"
import { ContainerRegistrationKeys, MedusaError } from "@medusajs/framework/utils"
import { createOrderFulfillmentWorkflow, createShippingOptionsWorkflow } from "@medusajs/medusa/core-flows"
import { readFileSync, writeFileSync } from "node:fs"
import { resolve } from "node:path"

export default async function prepareReturnDemo({ container }: ExecArgs) {
  const reportRoot = resolve(process.cwd(), "../../../commerceops_ai/reports")
  const demo = JSON.parse(readFileSync(resolve(reportRoot, "agent-live.json"), "utf8"))
  const orderId = demo.agent_order_id
  if (!orderId) throw new MedusaError(MedusaError.Types.INVALID_DATA, "Missing local demo order")
  const query = container.resolve(ContainerRegistrationKeys.QUERY)
  const { data: [order] } = await query.graph({ entity: "order", fields: ["id", "items.id", "items.quantity", "fulfillments.id"], filters: { id: orderId } })
  const { data: [location] } = await query.graph({ entity: "stock_location", fields: ["id"] })
  const { data: [shipping] } = await query.graph({ entity: "shipping_option", fields: ["id", "service_zone_id", "shipping_profile_id", "provider_id"] })
  if (!order || !location || !shipping) throw new MedusaError(MedusaError.Types.INVALID_DATA, "Incomplete demo fixture")
  let fulfillmentId = order.fulfillments?.[0]?.id
  if (!fulfillmentId) {
    const { result } = await createOrderFulfillmentWorkflow(container).run({ input: { order_id: orderId, location_id: location.id, items: order.items.map((item) => ({ id: item.id, quantity: item.quantity })) } })
    fulfillmentId = result.id
  }
  const { data: existing } = await query.graph({ entity: "shipping_option", fields: ["id"], filters: { name: "CommerceOps Test Return" } })
  let returnOption = existing[0]?.id
  if (!returnOption) {
    const { result } = await createShippingOptionsWorkflow(container).run({ input: [{ name: "CommerceOps Test Return", price_type: "flat", provider_id: shipping.provider_id, service_zone_id: shipping.service_zone_id, shipping_profile_id: shipping.shipping_profile_id, type: { label: "Demo Return", description: "Local sandbox only", code: "demo-return" }, prices: [{ currency_code: "eur", amount: 0 }], rules: [{ attribute: "enabled_in_store", value: "true", operator: "eq" }, { attribute: "is_return", value: "true", operator: "eq" }] }] })
    returnOption = result[0].id
  }
  writeFileSync(resolve(reportRoot, "return-fixture.json"), JSON.stringify({ order_id: orderId, items: order.items.map((item) => ({ id: item.id, quantity: item.quantity })), shipping_option_id: returnOption, location_id: location.id, fulfillment_id: fulfillmentId }, null, 2))
  console.log("Local demo order fulfilled; return option fixture saved")
}
