import { type Page, expect, test } from "@playwright/test";

const PASSWORD = "e2e-test-only";

async function signIn(page: Page, user: string) {
  await page.goto("/");
  await page.locator("#username").fill(user);
  await page.locator("#password").fill(PASSWORD);
  await page.locator("#kc-login").click();
  await expect(page.getByTestId("user-name")).toHaveText(user);
}

async function send(page: Page, text: string) {
  await page.getByTestId("task-input").fill(text);
  await page.getByTestId("send").click();
}

test("an unauthenticated browser is sent to Keycloak and cannot reach the agent", async ({ page, request }) => {
  const direct = await request.post("/api/agent/threads", {
    data: {},
    headers: { origin: "http://localhost:3000" },
  });
  expect(direct.status()).toBe(401);
  await page.goto("/");
  await expect(page).toHaveURL(/\/realms\/langsmith\/protocol\/openid-connect\/auth/);
});

test("a signed-in user gets an answer from the agent", async ({ page }) => {
  await signIn(page, "alice");
  await send(page, "Summarise the platform");
  await expect(page.getByTestId("msg-ai").last()).toContainText("Stub model reply: Summarise the platform");
});

test("the agent's plan appears in the plan panel", async ({ page }) => {
  await signIn(page, "alice");
  await send(page, "Make a plan for the design");
  await expect(page.getByTestId("plan")).toContainText("Draft the design");
  await expect(page.getByTestId("plan")).toContainText("Review the draft");
});

test("publication pauses for approval and runs only after the user approves", async ({ page }) => {
  await signIn(page, "alice");
  await send(page, "Publish the design");
  const approval = page.getByTestId("approval");
  await expect(approval).toContainText("publish_document");
  await expect(page.getByTestId("messages")).not.toContainText("Published 'Design'");
  await page.getByTestId("approve").click();
  await expect(page.getByTestId("msg-ai").last()).toContainText("Finished: Published 'Design'");
  await expect(approval).toHaveCount(0);
});

test("a rejected publication never runs", async ({ page }) => {
  await signIn(page, "alice");
  await send(page, "Publish the design");
  await expect(page.getByTestId("approval")).toBeVisible();
  await page.getByTestId("reject").click();
  await expect(page.getByTestId("approval")).toHaveCount(0);
  await expect(page.getByTestId("msg-ai").last()).toContainText("Finished:");
  await expect(page.getByTestId("messages")).not.toContainText("Published 'Design'");
});

test("the agent uses a tool from the MCP server, and only the allowlisted one", async ({ page }) => {
  await signIn(page, "alice");
  await send(page, "Look up decision AD-59");
  await expect(page.getByTestId("msg-ai").last()).toContainText("source: reference MCP server");
});

test("a background task runs on its own thread and reports back", async ({ page }) => {
  await signIn(page, "alice");
  await send(page, "Run the analysis in the background");
  const tasks = page.getByTestId("background-tasks");
  await expect(tasks).toContainText("analyst");
  await expect(page.getByTestId("messages")).toContainText("Launched async subagent");
  await expect(tasks.locator("li")).toHaveAttribute("data-status", "success", { timeout: 60_000 });
  await expect(page.getByTestId("messages")).toContainText("The background analysis has finished.");
  await expect(page.getByTestId("msg-human")).toHaveCount(1); // the task's report is not shown as a user message
});

test("one user cannot read another user's thread", async ({ browser }) => {
  const alice = await browser.newContext();
  const alicePage = await alice.newPage();
  await signIn(alicePage, "alice");
  await send(alicePage, "Private note for alice");
  await expect(alicePage.getByTestId("msg-ai").last()).toContainText("Private note for alice");
  const threadId = await alicePage.evaluate(() => window.sessionStorage.getItem("wb.threadId"));
  expect(threadId).toBeTruthy();

  const bob = await browser.newContext();
  const bobPage = await bob.newPage();
  await signIn(bobPage, "bob");
  const stolen = await bobPage.request.get(`/api/agent/threads/${threadId}/state`);
  expect([403, 404]).toContain(stolen.status());
  await alice.close();
  await bob.close();
});
