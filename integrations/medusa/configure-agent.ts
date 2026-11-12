import { ExecArgs } from "@medusajs/framework/types"
import { ContainerRegistrationKeys, MedusaError } from "@medusajs/framework/utils"
import { readFileSync, writeFileSync } from "node:fs"
import { resolve } from "node:path"

export default async function configureAgent({ container }: ExecArgs) {
  const query = container.resolve(ContainerRegistrationKeys.QUERY)
  const { data: keys } = await query.graph({ entity: "api_key", fields: ["token", "type"], filters: { type: "publishable" } })
  const { data: regions } = await query.graph({ entity: "region", fields: ["id"] })
  if (!keys[0]?.token || !regions[0]?.id) throw new MedusaError(MedusaError.Types.INVALID_DATA, "Seed is incomplete")
  const target = resolve(process.cwd(), "../../../commerceops_ai/.env")
  let text = readFileSync(target, "utf8")
  text = text.replace(/^MEDUSA_PUBLISHABLE_KEY=.*$/m, `MEDUSA_PUBLISHABLE_KEY=${keys[0].token}`)
  text = text.replace(/^MEDUSA_REGION_ID=.*$/m, `MEDUSA_REGION_ID=${regions[0].id}`)
  writeFileSync(target, text)
  console.log("Agent local configuration updated; no credentials displayed")
}
