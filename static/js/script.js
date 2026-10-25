/* FoodEase front end. One file, one init function per page.
   Prices are only ever DISPLAYED here. The server recalculates every total from the database. */
"use strict";

/* ---------- helpers ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const inr = (n) => {
  const value = Number(n) || 0;
  return new Intl.NumberFormat("en-IN", {
    style: "currency", currency: "INR",
    minimumFractionDigits: value % 1 ? 2 : 0, maximumFractionDigits: 2,
  }).format(value);
};

const parseDate = (s) => new Date(String(s).replace(" ", "T"));
const when = (s) => parseDate(s).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
const dayLabel = (s) => parseDate(s + " 00:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric" });

async function api(path, { method = "GET", body } = {}) {
  const init = { method, headers: {}, credentials: "same-origin" };
  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, init);
  } catch {
    throw new Error("Can't reach the server. Check that FoodEase is running.");
  }
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const err = new Error((data && data.error) || "Something went wrong. Try again.");
    err.status = res.status;
    throw err;
  }
  return data;
}

function toast(message, kind = "ok") {
  const el = document.createElement("div");
  el.className = "toast" + (kind === "error" ? " error" : "");
  el.textContent = message;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), 4200);
}

const guard = (fn) => async (...args) => {
  try { return await fn(...args); } catch (err) { toast(err.message, "error"); }
};

/* ---------- cart (kept in this browser; checked again by the server) ---------- */
const Cart = {
  key: "foodease_cart",
  read() {
    try { return JSON.parse(localStorage.getItem(this.key)) || {}; } catch { return {}; }
  },
  write(cart) {
    try { localStorage.setItem(this.key, JSON.stringify(cart)); } catch { /* storage blocked */ }
    renderCartBadges();
  },
  qty(id) { return (this.read()[id] || {}).qty || 0; },
  set(item, qty) {
    const cart = this.read();
    if (qty <= 0) delete cart[item.id];
    else cart[item.id] = { id: item.id, name: item.name, price: item.price, qty: Math.min(qty, 20) };
    this.write(cart);
  },
  lines() { return Object.values(this.read()); },
  count() { return this.lines().reduce((n, l) => n + l.qty, 0); },
  total() { return this.lines().reduce((n, l) => n + l.qty * l.price, 0); },
  clear() { this.write({}); },
};

function renderCartBadges() {
  const count = Cart.count();
  $("#cart-count").textContent = count;
  const bar = $("#cartbar");
  const onCart = document.body.dataset.page === "cart";
  if (count > 0 && !onCart) {
    bar.hidden = false;
    bar.innerHTML = `<span>View cart · ${count} ${count === 1 ? "item" : "items"}</span><strong>${inr(Cart.total())}</strong>`;
  } else {
    bar.hidden = true;
  }
}

function stepperHTML(qty) {
  return `<div class="stepper" role="group" aria-label="Quantity">
    <button type="button" data-act="dec" aria-label="Remove one">−</button>
    <output aria-live="polite">${qty}</output>
    <button type="button" data-act="inc" aria-label="Add one">+</button></div>`;
}

/* ---------- shared chrome ---------- */
function initChrome() {
  const page = document.body.dataset.page;
  const nav = { menu: "menu", cart: "menu", orders: "orders", admin: "admin" }[page];
  $$(".nav a").forEach((a) => { if (a.dataset.nav === nav) a.setAttribute("aria-current", "page"); });
  const logout = $("#logout");
  if (logout) {
    logout.addEventListener("click", guard(async () => {
      await api("/api/logout", { method: "POST" });
      location.href = "/";
    }));
  }
  renderCartBadges();
}

/* ---------- menu page ---------- */
function initMenu() {
  const state = { categories: [], items: [], active: 0, q: "" };
  const menuEl = $("#menu");
  const railEl = $("#rail");

  function renderRail() {
    const total = state.items.length;
    const all = `<button type="button" data-cat="0" aria-pressed="${state.active === 0}">All <span class="count">${total}</span></button>`;
    railEl.innerHTML = all + state.categories.map((c) =>
      `<button type="button" data-cat="${c.category_id}" aria-pressed="${state.active === c.category_id}">${esc(c.category_name)} <span class="count">${c.item_count}</span></button>`
    ).join("");
  }

  function dishAction(item) {
    if (!item.is_available) return `<span class="soldout">Sold out</span>`;
    const qty = Cart.qty(item.food_id);
    return qty ? stepperHTML(qty) : `<button class="btn btn-solid btn-small" type="button" data-act="inc">Add</button>`;
  }

  function renderMenu() {
    const q = state.q.toLowerCase();
    const items = state.items.filter((i) =>
      (!state.active || i.category_id === state.active) && (!q || i.name.toLowerCase().includes(q)));
    if (!items.length) {
      menuEl.innerHTML = `<p class="empty muted">${q ? `Nothing on the menu matches “${esc(state.q)}”. Try a different word.` : "No dishes in this category yet."}</p>`;
      return;
    }
    const groups = new Map();
    items.forEach((i) => {
      if (!groups.has(i.category_name)) groups.set(i.category_name, []);
      groups.get(i.category_name).push(i);
    });
    menuEl.innerHTML = [...groups].map(([name, list]) => `
      <section aria-labelledby="cat-${esc(name)}">
        <h2 id="cat-${esc(name)}">${esc(name)}</h2>
        <ul class="dishes">${list.map((i) => `
          <li class="dish ${i.is_available ? "" : "is-out"}" data-id="${i.food_id}">
            <div class="dish-main"><span class="dish-name">${esc(i.name)}</span><span class="leader" aria-hidden="true"></span><span class="dish-price">${inr(i.price)}</span></div>
            <div class="dish-action">${dishAction(i)}</div>
          </li>`).join("")}
        </ul>
      </section>`).join("");
  }

  railEl.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-cat]");
    if (!btn) return;
    state.active = Number(btn.dataset.cat);
    renderRail();
    renderMenu();
  });

  let timer;
  $("#search").addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => { state.q = e.target.value.trim(); renderMenu(); }, 120);
  });

  menuEl.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-act]");
    const row = e.target.closest(".dish");
    if (!btn || !row) return;
    const item = state.items.find((i) => i.food_id === Number(row.dataset.id));
    if (!item) return;
    const next = Cart.qty(item.food_id) + (btn.dataset.act === "inc" ? 1 : -1);
    if (next > 20) { toast("You can order up to 20 of each dish.", "error"); return; }
    Cart.set({ id: item.food_id, name: item.name, price: item.price }, next);
    const cell = $(".dish-action", row);
    cell.innerHTML = dishAction(item);
    const focusTarget = $(`[data-act="${btn.dataset.act}"]`, cell) || $("[data-act]", cell);
    if (focusTarget) focusTarget.focus();
  });

  api("/api/menu").then((data) => {
    state.categories = data.categories;
    state.items = data.items;
    // Keep saved cart prices in step with the live menu
    const cart = Cart.read();
    Object.keys(cart).forEach((id) => {
      const live = data.items.find((i) => i.food_id === Number(id));
      if (!live || !live.is_available) delete cart[id];
      else { cart[id].price = live.price; cart[id].name = live.name; }
    });
    Cart.write(cart);
    renderRail();
    renderMenu();
  }).catch((err) => { menuEl.innerHTML = `<p class="form-error">${esc(err.message)}</p>`; });
}

/* ---------- cart page ---------- */
function initCart() {
  const root = $("#cart-root");
  const loggedIn = !!document.body.dataset.role;
  let method = "UPI";
  let menu = null;

  function render() {
    const lines = Cart.lines();
    if (!lines.length) {
      root.className = "";
      root.innerHTML = `<div class="empty"><p>Your cart is empty.</p><a class="btn btn-solid" href="/">Browse the menu</a></div>`;
      return;
    }
    root.className = "cart-layout";
    const payOptions = [
      ["UPI", "UPI", "Pay now"], ["Card", "Card", "Pay now"], ["Cash", "Cash on delivery", "Pay when it arrives"],
    ].map(([value, label, hint]) => `
      <label class="pay-option"><input type="radio" name="method" value="${value}" ${method === value ? "checked" : ""}>
        <span>${label}<small>${hint}</small></span></label>`).join("");
    root.innerHTML = `
      <ul class="cart-lines">${lines.map((l) => `
        <li class="cart-line" data-id="${l.id}">
          <div><div class="name">${esc(l.name)}</div><div class="each">${inr(l.price)} each</div></div>
          ${stepperHTML(l.qty)}
          <div class="line-total">${inr(l.price * l.qty)}</div>
        </li>`).join("")}
      </ul>
      <aside class="checkout-box">
        <h2>Checkout</h2>
        <div class="sum-row"><span>Total</span><span>${inr(Cart.total())}</span></div>
        <fieldset><legend>Payment</legend>${payOptions}</fieldset>
        ${loggedIn
          ? `<button class="btn btn-solid btn-wide" id="place" type="button">Place order</button>`
          : `<div class="notice">Log in to place your order. Your cart will be waiting.</div>
             <a class="btn btn-solid btn-wide" href="/login?next=/cart">Log in to order</a>`}
        <p class="muted" style="margin:12px 0 0;font-size:.85rem">Card and UPI are simulated in this project: no real payment is taken.</p>
      </aside>`;
  }

  root.addEventListener("click", guard(async (e) => {
    const btn = e.target.closest("[data-act]");
    const row = e.target.closest(".cart-line");
    if (btn && row) {
      const id = Number(row.dataset.id);
      const line = Cart.read()[id];
      const next = line.qty + (btn.dataset.act === "inc" ? 1 : -1);
      if (next > 20) return toast("You can order up to 20 of each dish.", "error");
      Cart.set(line, next);
      render();
      return;
    }
    if (e.target.id === "place") {
      const button = e.target;
      button.disabled = true;
      button.textContent = "Placing order…";
      try {
        const result = await api("/api/orders", {
          method: "POST",
          body: { method, items: Cart.lines().map((l) => ({ food_id: l.id, quantity: l.qty })) },
        });
        Cart.clear();
        root.className = "";
        root.innerHTML = `<div class="success"><h2>Order #${result.order_id} placed</h2>
          <p>Your total is ${inr(result.total)}. We'll start preparing it shortly.</p>
          <a class="btn btn-solid" href="/orders">Track your order</a></div>`;
      } catch (err) {
        button.disabled = false;
        button.textContent = "Place order";
        if (err.status === 401) { location.href = "/login?next=/cart"; return; }
        throw err;
      }
    }
  }));

  root.addEventListener("change", (e) => {
    if (e.target.name === "method") method = e.target.value;
  });

  // Refresh names, prices and availability from the live menu before showing the cart
  api("/api/menu").then((data) => {
    menu = data;
    const cart = Cart.read();
    let removed = 0;
    Object.keys(cart).forEach((id) => {
      const live = data.items.find((i) => i.food_id === Number(id));
      if (!live || !live.is_available) { delete cart[id]; removed++; }
      else { cart[id].price = live.price; cart[id].name = live.name; }
    });
    Cart.write(cart);
    render();
    if (removed) toast(`${removed} sold-out ${removed === 1 ? "item was" : "items were"} removed from your cart.`, "error");
  }).catch(() => render());
}

/* ---------- my orders page ---------- */
const STEPS = ["Placed", "Preparing", "Out for Delivery", "Delivered"];

function statusBadge(status) {
  const kind = status === "Delivered" ? "good" : status === "Cancelled" ? "bad" : "";
  return `<span class="badge ${kind}">${esc(status)}</span>`;
}
function payBadge(order) {
  const s = order.payment_status;
  const kind = s === "Paid" ? "good" : s === "Failed" ? "bad" : "plain";
  return `<span class="badge ${kind}">${esc(order.payment_method || "")} · ${esc(s || "—")}</span>`;
}

function trackerHTML(order) {
  if (order.status === "Cancelled") {
    const at = order.history.find((h) => h.new_status === "Cancelled");
    return `<p class="muted">Cancelled${at ? " on " + when(at.changed_at) : ""}.</p>`;
  }
  const index = STEPS.indexOf(order.status);
  return `<ol class="tracker" aria-label="Order progress">${STEPS.map((step, i) => {
    const hit = order.history.find((h) => h.new_status === step);
    const cls = i < index ? "done" : i === index ? "current" : "";
    return `<li class="${cls}" ${i === index ? 'aria-current="step"' : ""}>${step}${hit ? `<time>${when(hit.changed_at)}</time>` : ""}</li>`;
  }).join("")}</ol>`;
}

function initOrders() {
  const root = $("#orders-root");

  async function load() {
    const { orders } = await api("/api/orders");
    if (!orders.length) {
      root.innerHTML = `<div class="empty"><p>You haven't ordered anything yet.</p><a class="btn btn-solid" href="/">Browse the menu</a></div>`;
      return;
    }
    root.innerHTML = orders.map((o) => `
      <article class="order" data-id="${o.order_id}">
        <div class="order-top"><h2>Order #${o.order_id}</h2><span class="order-meta">${when(o.order_date)}</span></div>
        ${trackerHTML(o)}
        <ul class="lines">${o.items.map((i) =>
          `<li><span>${i.quantity} × ${esc(i.name)}</span><span>${inr(i.quantity * i.unit_price)}</span></li>`).join("")}</ul>
        <div class="order-foot">
          <div>${statusBadge(o.status)} ${payBadge(o)}</div>
          <div class="actions">
            <strong>${inr(o.total_amount)}</strong>
            ${o.status === "Placed" ? `<button class="btn btn-danger btn-small" data-cancel="${o.order_id}" type="button">Cancel order</button>` : ""}
          </div>
        </div>
      </article>`).join("");
  }

  root.addEventListener("click", guard(async (e) => {
    const btn = e.target.closest("[data-cancel]");
    if (!btn) return;
    if (!confirm(`Cancel order #${btn.dataset.cancel}?`)) return;
    await api(`/api/orders/${btn.dataset.cancel}/cancel`, { method: "POST" });
    toast("Order cancelled.");
    await load();
  }));

  load().catch((err) => { root.innerHTML = `<p class="form-error">${esc(err.message)}</p>`; });
  setInterval(() => { if (!document.hidden) load().catch(() => {}); }, 15000);
}

/* ---------- login / register ---------- */
function initAuth() {
  const form = $("#auth-form");
  const errorEl = $("#form-error");
  const isRegister = document.body.dataset.page === "register";
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.textContent = "";
    const body = Object.fromEntries(new FormData(form));
    const button = $("button[type=submit]", form);
    button.disabled = true;
    try {
      await api(isRegister ? "/api/register" : "/api/login", { method: "POST", body });
      const next = new URLSearchParams(location.search).get("next") || "/";
      location.href = next.startsWith("/") && !next.startsWith("//") ? next : "/";
    } catch (err) {
      errorEl.textContent = err.message;
      button.disabled = false;
    }
  });
}

/* ---------- admin ---------- */
function initAdmin() {
  const root = $("#admin-root");
  const tabs = $$(".tab");
  let current = "overview";
  let menuData = null;

  const table = (head, rows, empty) => rows.length
    ? `<div class="table-wrap"><table><thead><tr>${head.map(([label, cls]) => `<th class="${cls || ""}">${label}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`
    : `<p class="muted">${empty}</p>`;

  async function overview() {
    const r = await api("/api/admin/reports");
    const max = Math.max(...r.last7.map((d) => Number(d.revenue)), 1);
    root.innerHTML = `
      <dl class="stat-strip">
        <div class="stat"><dt>Revenue</dt><dd>${inr(r.stats.revenue)}</dd></div>
        <div class="stat"><dt>Orders</dt><dd>${r.stats.orders_total}</dd></div>
        <div class="stat"><dt>In progress</dt><dd>${r.stats.orders_active}</dd></div>
        <div class="stat"><dt>Customers</dt><dd>${r.stats.customers}</dd></div>
      </dl>
      <div class="split">
        <section>
          <h2>Sales, last 7 days</h2>
          <div class="bars" role="img" aria-label="Daily revenue for the last seven days">${r.last7.map((d) => `
            <div class="bar ${Number(d.revenue) ? "" : "zero"}"><span>${Number(d.revenue) ? inr(d.revenue) : ""}</span><i style="height:${Math.round((Number(d.revenue) / max) * 150)}px"></i></div>`).join("")}</div>
          <div class="bar-days">${r.last7.map((d) => `<span>${dayLabel(d.day)}</span>`).join("")}</div>
        </section>
        <section>
          <h2>Most ordered</h2>
          ${table([["Dish"], ["Sold", "num"]], r.popular.slice(0, 5).map((p) =>
            `<tr><td>${esc(p.name)}</td><td class="num">${p.units_sold}</td></tr>`), "No orders yet.")}
        </section>
      </div>`;
  }

  async function orders(status = "") {
    const { orders: list } = await api("/api/admin/orders" + (status ? `?status=${encodeURIComponent(status)}` : ""));
    const rows = list.map((o) => `
      <tr data-id="${o.order_id}">
        <td>#${o.order_id}<br><span class="muted">${when(o.order_date)}</span></td>
        <td>${esc(o.customer_name)}<br><span class="muted">${esc(o.customer_phone)}</span></td>
        <td>${o.items.map((i) => `${i.quantity} × ${esc(i.name)}`).join("<br>")}</td>
        <td class="num">${inr(o.total_amount)}<br>${payBadge(o)}</td>
        <td>${statusBadge(o.status)}</td>
        <td><div class="actions">${o.next.map((s) =>
          `<button type="button" class="btn btn-small ${s === "Cancelled" ? "btn-danger" : "btn-solid"}" data-status="${esc(s)}">${s === "Cancelled" ? "Cancel" : "Mark " + esc(s.toLowerCase())}</button>`).join("") || '<span class="muted">Done</span>'}</div></td>
      </tr>`);
    root.innerHTML = `
      <div class="toolbar"><label>Show
        <select id="status-filter"><option value="">All orders</option>
          ${["Placed", "Preparing", "Out for Delivery", "Delivered", "Cancelled"].map((s) => `<option ${s === status ? "selected" : ""}>${s}</option>`).join("")}
        </select></label></div>
      ${table([["Order"], ["Customer"], ["Items"], ["Total", "num"], ["Status"], ["Update"]], rows, "No orders match.")}`;
  }

  async function menu() {
    menuData = await api("/api/admin/menu");
    const catOptions = (selected) => menuData.categories.map((c) =>
      `<option value="${c.category_id}" ${c.category_id === selected ? "selected" : ""}>${esc(c.category_name)}</option>`).join("");
    root.innerHTML = `
      <h2>Add a dish</h2>
      <form class="inline-form" id="add-food">
        <label>Name<input name="name" required maxlength="100"></label>
        <label>Price (₹)<input name="price" type="number" min="0" step="0.01" required></label>
        <label>Category<select name="category_id">${catOptions()}</select></label>
        <label class="check"><input type="checkbox" name="is_available" checked> Available</label>
        <button class="btn btn-solid" type="submit">Add dish</button>
      </form>
      <h2>Menu items</h2>
      ${table([["Name"], ["Price (₹)"], ["Category"], ["Available"], [""]], menuData.items.map((i) => `
        <tr data-id="${i.food_id}">
          <td><input data-f="name" value="${esc(i.name)}" maxlength="100" aria-label="Name"></td>
          <td><input data-f="price" type="number" min="0" step="0.01" value="${i.price}" aria-label="Price" style="width:100px"></td>
          <td><select data-f="category_id" aria-label="Category">${catOptions(i.category_id)}</select></td>
          <td><input data-f="is_available" type="checkbox" ${i.is_available ? "checked" : ""} aria-label="Available"></td>
          <td><div class="actions"><button type="button" class="btn btn-solid btn-small" data-save>Save</button>
            <button type="button" class="btn btn-danger btn-small" data-delete>Delete</button></div></td>
        </tr>`), "No dishes yet. Add the first one above.")}
      <h2 class="section-gap">Categories</h2>
      <form class="inline-form" id="add-cat" style="grid-template-columns:1fr auto">
        <label>New category<input name="category_name" required maxlength="60"></label>
        <button class="btn btn-solid" type="submit">Add category</button>
      </form>
      <p class="muted">${menuData.categories.map((c) => `${esc(c.category_name)} (${c.item_count})`).join(" · ")}</p>`;
  }

  async function reports() {
    const r = await api("/api/admin/reports");
    root.innerHTML = `
      <div class="split">
        <section><h2>Dishes by units sold</h2>
          ${table([["Dish"], ["Units", "num"], ["Revenue", "num"]], r.popular.map((p) =>
            `<tr><td>${esc(p.name)}</td><td class="num">${p.units_sold}</td><td class="num">${inr(p.revenue)}</td></tr>`), "No orders yet.")}</section>
        <section><h2>Revenue by category</h2>
          ${table([["Category"], ["Units", "num"], ["Revenue", "num"]], r.by_category.map((c) =>
            `<tr><td>${esc(c.category_name)}</td><td class="num">${c.units_sold}</td><td class="num">${inr(c.revenue)}</td></tr>`), "No orders yet.")}</section>
      </div>
      <section class="section-gap"><h2>Top customers</h2>
        ${table([["Customer"], ["Orders", "num"], ["Spent", "num"]], r.top_customers.map((c) =>
          `<tr><td>${esc(c.name)}</td><td class="num">${c.orders}</td><td class="num">${inr(c.spent)}</td></tr>`), "No orders yet.")}</section>
      <p class="muted section-gap">Cancelled orders are left out of every figure on this page.</p>`;
  }

  const views = { overview, orders, menu, reports };
  const show = async (name) => {
    current = name;
    tabs.forEach((t) => t.setAttribute("aria-selected", String(t.dataset.tab === name)));
    try { await views[name](); } catch (err) { root.innerHTML = `<p class="form-error">${esc(err.message)}</p>`; }
  };

  tabs.forEach((t) => t.addEventListener("click", () => show(t.dataset.tab)));

  root.addEventListener("change", (e) => {
    if (e.target.id === "status-filter") orders(e.target.value);
  });

  root.addEventListener("click", guard(async (e) => {
    const statusBtn = e.target.closest("[data-status]");
    if (statusBtn) {
      const id = statusBtn.closest("tr").dataset.id;
      const status = statusBtn.dataset.status;
      if (status === "Cancelled" && !confirm(`Cancel order #${id}?`)) return;
      await api(`/api/admin/orders/${id}/status`, { method: "PATCH", body: { status } });
      toast(`Order #${id} is now ${status.toLowerCase()}.`);
      await orders($("#status-filter").value);
      return;
    }
    const row = e.target.closest("tr[data-id]");
    if (e.target.closest("[data-save]") && row) {
      const field = (f) => $(`[data-f="${f}"]`, row);
      await api(`/api/admin/foods/${row.dataset.id}`, {
        method: "PUT",
        body: { name: field("name").value, price: field("price").value,
                category_id: field("category_id").value, is_available: field("is_available").checked },
      });
      toast("Dish saved.");
      await menu();
    } else if (e.target.closest("[data-delete]") && row) {
      const name = $('[data-f="name"]', row).value;
      if (!confirm(`Delete “${name}” from the menu?`)) return;
      await api(`/api/admin/foods/${row.dataset.id}`, { method: "DELETE" });
      toast("Dish deleted.");
      await menu();
    }
  }));

  root.addEventListener("submit", guard(async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    if (e.target.id === "add-food") {
      data.is_available = e.target.elements.is_available.checked;
      await api("/api/admin/foods", { method: "POST", body: data });
      toast("Dish added.");
    } else if (e.target.id === "add-cat") {
      await api("/api/admin/categories", { method: "POST", body: data });
      toast("Category added.");
    } else return;
    await menu();
  }));

  show("overview");
}

/* ---------- start ---------- */
document.addEventListener("DOMContentLoaded", () => {
  initChrome();
  const init = { menu: initMenu, cart: initCart, orders: initOrders, admin: initAdmin, login: initAuth, register: initAuth }[document.body.dataset.page];
  if (init) init();
});
