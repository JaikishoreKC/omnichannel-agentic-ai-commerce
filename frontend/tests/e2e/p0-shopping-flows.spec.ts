import { expect, type Page, test } from "@playwright/test";

function uniqueEmail(prefix: string): string {
  const stamp = Date.now();
  const rand = Math.floor(Math.random() * 100000);
  return `${prefix}-${stamp}-${rand}@example.com`;
}

async function registerUser(page: Page, prefix: string): Promise<void> {
  const isLoginPage = page.url().includes("/login");
  if (!isLoginPage) {
    await page.getByTestId("login-link").click();
  }

  // Switch to register mode
  await page.getByText("Sign Up").click();

  await page.getByTestId("name-input").fill("E2E User");
  await page.getByTestId("email-input").fill(uniqueEmail(prefix));
  await page.getByTestId("password-input").fill("SecurePass123!");
  await page.getByTestId("auth-submit-button").click();

  // Wait for redirect to account or home
  await expect(page).not.toHaveURL(/\/login/);
}

async function addFirstProductToCart(page: Page): Promise<void> {
  // On home page, find first product card
  const addToCartButton = page.locator("[data-testid^='add-to-cart-']").first();
  await expect(addToCartButton).toBeVisible();
  await addToCartButton.click();
  // Check cart badge in navbar
  await expect(page.getByTestId("cart-item-count")).toBeVisible();
}

async function sendChat(page: Page, text: string): Promise<void> {
  const chatInput = page.getByTestId("chat-input");
  const sendButton = page.getByTestId("chat-send-button");

  // Open chat if not open
  const isChatOpen = await page.getByTestId("chat-log").isVisible();
  if (!isChatOpen) {
    await page.locator("button:has(svg.lucide-message-square)").click();
  }

  await expect(page.getByTestId("chat-ready")).toContainText("connected");

  await chatInput.fill(text);
  await sendButton.click();

  // Wait for typing indicator to disappear
  await expect(page.locator(".animate-bounce")).toHaveCount(0, { timeout: 10000 });
}

test("guest cart survives account creation", async ({ page }) => {
  await page.goto("/");
  await addFirstProductToCart(page);
  await expect(page.getByTestId("cart-item-count")).toContainText("1");

  await registerUser(page, "guest-cart-transfer");
  await page.goto("/cart");
  await expect(page.getByTestId("cart-list")).toBeVisible();
  // Should have at least one item
  const itemCount = await page.locator("[data-testid='cart-list'] > div").count();
  expect(itemCount).toBeGreaterThan(0);
});

test("catalog product opens dedicated detail page", async ({ page }) => {
  await page.goto("/");

  const productCard = page.locator("a[href^='/products/']").first();
  const productId = (await productCard.getAttribute("href"))?.split("/").pop();

  await productCard.click();
  await expect(page).toHaveURL(new RegExp(`/products/${productId}$`));

  // Verify detail page elements
  await expect(page.locator("h1")).toBeVisible();
  await expect(page.getByText("Add to Bag")).toBeVisible();
});

test("authenticated user can checkout from cart", async ({ page }) => {
  await page.goto("/");
  await registerUser(page, "auth-checkout");
  await addFirstProductToCart(page);

  await page.goto("/cart");
  await page.getByTestId("checkout-button").click();

  // Mock alert handling or check for redirect to account
  page.on('dialog', dialog => dialog.accept());
  await expect(page).toHaveURL(/\/account/);
});

test("chat-driven interacton works", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("button:has(svg.lucide-message-square)")).toBeVisible();

  // Open chat
  await page.locator("button:has(svg.lucide-message-square)").click();
  await expect(page.getByTestId("chat-ready")).toContainText("connected");

  await sendChat(page, "hello");
  await expect(page.getByTestId("chat-log")).toContainText("assistant");
});

test("chat history is restored after reload", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("session-id")).not.toContainText("initializing");
  await registerUser(page, "history-restore");
  await page.reload();
  await expect(page.getByTestId("session-id")).not.toContainText("initializing");
  await expect(page.getByTestId("chat-ready")).toContainText("connected");

  await sendChat(page, "show me running shoes");
  await expect(page.getByTestId("chat-log")).toContainText("Top result");

  await page.reload();
  await expect(page.getByTestId("session-id")).not.toContainText("initializing");
  await expect(page.getByTestId("chat-ready")).toContainText("connected");

  await expect
    .poll(async () => (await page.getByTestId("chat-log").textContent()) ?? "")
    .toContain("You: show me running shoes");
  await expect
    .poll(async () => (await page.getByTestId("chat-log").textContent()) ?? "")
    .toContain("Top result");
});
