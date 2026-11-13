const assert = require("node:assert/strict")
const { createRequire } = require("node:module")
const path = require("node:path")
const test = require("node:test")

const backendRequire = createRequire(path.join(__dirname, "..", "package.json"))
const medusaEntry = backendRequire.resolve("@medusajs/medusa")
const providerEntry = backendRequire.resolve("@medusajs/notification-sendgrid", {
  paths: [path.dirname(medusaEntry)],
})
const helpersEntry = backendRequire.resolve("@sendgrid/helpers", {
  paths: [path.dirname(providerEntry)],
})
const deepmergeEntry = backendRequire.resolve("deepmerge", {
  paths: [path.dirname(helpersEntry)],
})
const deepmerge = backendRequire(deepmergeEntry)

test("the production SendGrid deepmerge path ignores __proto__", () => {
  const source = JSON.parse('{"__proto__":{"polluted":true},"safe":{"value":true}}')
  const merged = deepmerge(Object.create(null), source)

  assert.equal(Object.getPrototypeOf(merged), Object.prototype)
  assert.equal(Object.hasOwn(merged, "__proto__"), false)
  assert.equal(({}).polluted, undefined)
  assert.deepEqual(merged.safe, { value: true })
})
