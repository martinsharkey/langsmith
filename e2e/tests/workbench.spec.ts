import { type Page, expect, test } from "@playwright/test";

const PASSWORD = "e2e-test-only-password";
const ORIGIN = "http://localhost:3000";
const STUB_MODEL = "http://127.0.0.1:9000";

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

/** Chooses a decision for each pending action, in order, then sends them together. */
async function decide(page: Page, ...choices: ("approve" | "reject")[]) {
  const submit = page.getByTestId("submit-decisions");
  for (const [i, choice] of choices.entries()) {
    await expect(submit).toBeDisabled();
    await page.getByTestId(`${choice}-${i}`).click();
  }
  await submit.click();
}

test("an unauthenticated browser is sent to Keycloak and cannot reach the agent", async ({ page, request }) => {
  const direct = await request.post("/api/agent/threads", {
    data: {},
    headers: { origin: ORIGIN },
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

test("the page allows scripts only by nonce", async ({ page }) => {
  await signIn(page, "alice");
  const response = await page.goto("/");
  const policy = response?.headers()["content-security-policy"] ?? "";
  const scripts = policy.split(";").map((d) => d.trim()).find((d) => d.startsWith("script-src ")) ?? "";
  expect(scripts).toMatch(/'nonce-[^']+'/);
  expect(scripts).not.toContain("unsafe-inline");
  await send(page, "Scripts still run");
  await expect(page.getByTestId("msg-ai").last()).toContainText("Stub model reply: Scripts still run");
});

test("a message that mentions task notifications is still shown as the user's", async ({ page }) => {
  await signIn(page, "alice");
  await send(page, "What is a <task-notification> tag?");
  await expect(page.getByTestId("msg-ai").last()).toContainText("Stub model reply:");
  await expect(page.getByTestId("msg-human")).toContainText("What is a <task-notification> tag?");
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
  await decide(page, "approve");
  await expect(page.getByTestId("msg-ai").last()).toContainText("Finished: Published 'Design'");
  await expect(approval).toHaveCount(0);
});

test("a rejected publication never runs", async ({ page }) => {
  await signIn(page, "alice");
  await send(page, "Publish the design");
  await expect(page.getByTestId("approval")).toBeVisible();
  await decide(page, "reject");
  await expect(page.getByTestId("approval")).toHaveCount(0);
  await expect(page.getByTestId("msg-ai").last()).toContainText("Finished:");
  await expect(page.getByTestId("messages")).not.toContainText("Published 'Design'");
});

test("two pending publications are decided one by one: only the approved one runs", async ({ page }) => {
  await signIn(page, "alice");
  await send(page, "Publish two documents");
  const approval = page.getByTestId("approval");
  await expect(approval.getByTestId("action")).toHaveCount(2);
  await expect(approval.getByTestId("action").nth(0)).toContainText("Alpha");
  await expect(approval.getByTestId("action").nth(1)).toContainText("Beta");
  await decide(page, "approve", "reject");
  await expect(approval).toHaveCount(0);
  await expect(page.getByTestId("msg-ai").last()).toContainText("Published 'Alpha'");
  await expect(page.getByTestId("messages")).not.toContainText("Published 'Beta'");
});

test("the agent uses a read-only MCP tool without a pause, and never sees the tool left off the allowlist", async ({ page, request }) => {
  await signIn(page, "alice");
  await send(page, "Look up decision AD-59");
  await expect(page.getByTestId("msg-ai").last()).toContainText("source: reference MCP server");
  await expect(page.getByTestId("approval")).toHaveCount(0);
  const offered = (await (await request.get(`${STUB_MODEL}/offered-tools`)).json()) as { tools: string[] };
  expect(offered.tools).toContain("lookup_reference");
  expect(offered.tools).not.toContain("delete_reference");
});

test("an allowlisted MCP tool that writes pauses for approval", async ({ page }) => {
  await signIn(page, "alice");
  await send(page, "File a note on decision AD-59");
  const approval = page.getByTestId("approval");
  await expect(approval).toContainText("file_reference_note");
  await expect(page.getByTestId("messages")).not.toContainText("Note filed");
  await decide(page, "approve");
  await expect(page.getByTestId("msg-ai").last()).toContainText("Finished: Note filed for AD-59");
});

test("a background task runs on its own thread and reports back", async ({ page }) => {
  await signIn(page, "alice");
  await send(page, "Run the analysis in the background");
  const tasks = page.getByTestId("background-tasks");
  await expect(tasks).toContainText("analyst");
  await expect(page.getByTestId("messages")).toContainText("Launched async subagent");
  await expect(tasks.locator("li")).toHaveAttribute("data-status", "success", { timeout: 60_000 });
  await expect(page.getByTestId("messages")).toContainText("The background analysis has finished.");
  // DIAGNOSTIC (temporary): what the thread state and the screen hold for human messages.
  const threadId = await page.evaluate(() => window.sessionStorage.getItem("wb.threadId"));
  const state = (await (await page.request.get(`/api/agent/threads/${threadId}/state`)).json()) as {
    values: { messages: { id?: string; type?: string; additional_kwargs?: Record<string, unknown> }[] };
  };
  console.log("state", JSON.stringify(state.values.messages.map((m) => [m.type, m.id, Object.keys(m.additional_kwargs ?? {})])));
  console.log("screen", JSON.stringify(await page.getByTestId("msg-human").evaluateAll((els) => els.map((e) => [e.getAttribute("data-message-id"), e.textContent?.slice(0, 60)]))));
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

test("only an agent administrator can create or change an assistant", async ({ browser }) => {
  const admin = await browser.newContext();
  const adminPage = await admin.newPage();
  await signIn(adminPage, "carol");
  const created = await adminPage.request.post("/api/agent/assistants", {
    data: { graph_id: "agent", name: "e2e-admin-check" },
    headers: { origin: ORIGIN },
  });
  expect(created.status()).toBe(200);
  const assistantId = ((await created.json()) as { assistant_id: string }).assistant_id;

  const user = await browser.newContext();
  const userPage = await user.newPage();
  await signIn(userPage, "alice");
  const userCreate = await userPage.request.post("/api/agent/assistants", {
    data: { graph_id: "agent", name: "e2e-user-check" },
    headers: { origin: ORIGIN },
  });
  expect(userCreate.status()).toBe(403);
  const userUpdate = await userPage.request.patch(`/api/agent/assistants/${assistantId}`, {
    data: { metadata: { changed_by: "user" } },
    headers: { origin: ORIGIN },
  });
  expect(userUpdate.status()).toBe(403);

  const adminUpdate = await adminPage.request.patch(`/api/agent/assistants/${assistantId}`, {
    data: { metadata: { changed_by: "admin" } },
    headers: { origin: ORIGIN },
  });
  expect(adminUpdate.status()).toBe(200);
  await admin.close();
  await user.close();
});
