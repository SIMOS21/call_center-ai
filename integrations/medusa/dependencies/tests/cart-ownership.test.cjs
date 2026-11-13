const assert = require("node:assert/strict")
const fs = require("node:fs")
const Module = require("node:module")
const path = require("node:path")
const test = require("node:test")
const ts = require("typescript")

const filename = path.resolve(__dirname, "../src/api/commerceops-ownership.ts")
const source = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText
const compiled = new Module(filename, module)
compiled.paths = Module._nodeModulePaths(path.dirname(filename))
compiled._compile(source, filename)
const { ensureCustomerCartOwner, ensureCartOwner, ensureReturnOwner } = compiled.exports

async function check(middleware, owner, actor, body = {}) {
  const state = { next: false, status: null, query: null }
  const req = {
    params: { id: "cart_fixture" }, body,
    auth_context: actor ? { actor_id: actor } : undefined,
    scope: { resolve: () => ({ graph: async (query) => {
      state.query = query
      return { data: owner === undefined ? [] : [{ id: "cart_fixture", customer_id: owner }] }
    } }) },
  }
  const res = {
    status: (value) => {
      state.status = value
      return res
    },
    json: () => res,
  }
  await middleware(req, res, () => { state.next = true })
  return state
}

test("customer cart requires its owner, including unauthenticated requests", async () => {
  assert.equal((await check(ensureCustomerCartOwner, "A", "A")).next, true)
  assert.equal((await check(ensureCustomerCartOwner, "A", "B")).status, 403)
  assert.equal((await check(ensureCustomerCartOwner, "A", null)).status, 403)
  const missing = await check(ensureCustomerCartOwner, undefined, "A")
  assert.equal(missing.status, 404)
  assert.deepEqual(missing.query.filters, { id: "cart_fixture" })
})

test("anonymous storefront cart flow remains usable", async () => {
  assert.equal((await check(ensureCustomerCartOwner, null, null)).next, true)
  assert.equal((await check(ensureCustomerCartOwner, null, "A")).next, true)
})

test("strict checkout owner check still denies anonymous and foreign carts", async () => {
  assert.equal((await check(ensureCartOwner, "A", "A")).next, true)
  assert.equal((await check(ensureCartOwner, "A", "B")).status, 403)
  assert.equal((await check(ensureCartOwner, null, "A")).status, 403)
})

test("return middleware still rejects financial receive_now requests", async () => {
  const result = await check(ensureReturnOwner, "A", "A", { order_id: "order_fixture", receive_now: true })
  assert.equal(result.status, 400)
  assert.equal(result.next, false)
})
