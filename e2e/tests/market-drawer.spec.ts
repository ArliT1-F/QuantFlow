import { expect, test } from "@playwright/test";

function marketPayload() {
  return {
    results: [
      {
        symbol: "TOKA/USDT",
        name: "Token A",
        price: 0.0123,
        change_percent: 18.4,
        volume: 250000,
        liquidity: 120000,
        market_cap: 900000,
        chain: "solana",
        dex: "pumpfun",
        pair_address: "pair-a",
        url: "https://dexscreener.com/solana/pair-a",
        boost_amount: 55,
        boost_count: 8
      },
      {
        symbol: "TOKB/USDT",
        name: "Token B",
        price: 0.0042,
        change_percent: -3.1,
        volume: 95000,
        liquidity: 66000,
        market_cap: 300000,
        chain: "solana",
        dex: "pumpfun",
        pair_address: "pair-b",
        url: "",
        boost_amount: 12,
        boost_count: 3
      }
    ],
    count: 2,
    total: 2,
    page: 1,
    page_size: 50,
    total_pages: 1,
    mode: "top",
    sort: "boosts",
    chain: "solana",
    min_liquidity: 0,
    effective_min_liquidity: 0,
    summary: {
      volume: 345000,
      liquidity: 186000,
      avg_change_percent: 7.65
    },
    meta: {
      as_of: "2026-01-01T00:00:00+00:00",
      is_stale: false,
      age_seconds: 1,
      source_counts: { top: 30, latest: 30, profiles: 30, tokens: 60, pairs: 2 }
    },
    timestamp: "2026-01-01T00:00:01+00:00"
  };
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path.endsWith("/trading/status")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "stopped",
          is_running: false,
          strategies: ["momentum"],
          market_source: "DexScreener (solana)",
          market_chain: "solana",
          okx_enabled: false,
          okx_demo: true,
          dexscreener_enabled: true,
          yahoo_enabled: false,
          alpha_vantage_enabled: false,
          timestamp: "2026-01-01T00:00:00+00:00"
        })
      });
    }
    if (path.endsWith("/portfolio/overview")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          portfolio_metrics: {
            total_value: 10000,
            cash_balance: 10000,
            invested_amount: 0,
            total_pnl: 0,
            num_positions: 0
          },
          timestamp: "2026-01-01T00:00:00+00:00"
        })
      });
    }
    if (path.endsWith("/portfolio/performance")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ performance: [], count: 0, timestamp: "2026-01-01T00:00:00+00:00" })
      });
    }
    if (path.endsWith("/portfolio/positions")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ positions: [], count: 0, timestamp: "2026-01-01T00:00:00+00:00" })
      });
    }
    if (path.endsWith("/portfolio/trades")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ trades: [], count: 0, timestamp: "2026-01-01T00:00:00+00:00" })
      });
    }
    if (path.endsWith("/trading/events")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ events: [], count: 0, timestamp: "2026-01-01T00:00:00+00:00" })
      });
    }
    if (path.endsWith("/market/dexscreener/boosts")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(marketPayload())
      });
    }
    if (path.endsWith("/settings/trading")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          settings: {
            max_position_size_percent: 10,
            stop_loss_percent: 5,
            take_profit_percent: 15
          },
          timestamp: "2026-01-01T00:00:00+00:00"
        })
      });
    }

    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ timestamp: "2026-01-01T00:00:00+00:00" })
    });
  });
});

test("opens drawer when clicking market row and closes with Escape", async ({ page }) => {
  await page.goto("/static/index.html");
  await page.locator('.nav-link[data-section="market"]').click();
  await expect(page.locator("#market-data-table tr.market-row").first()).toBeVisible();
  await page.locator("#market-data-table tr.market-row").first().click();

  await expect(page.locator("#market-detail-drawer")).toHaveClass(/open/);
  await expect(page.locator("#market-detail-title")).toContainText("TOKA");

  await page.keyboard.press("Escape");
  await expect(page.locator("#market-detail-drawer")).not.toHaveClass(/open/);
});

test("external icon opens new tab without opening drawer", async ({ page }) => {
  await page.goto("/static/index.html");
  await page.locator('.nav-link[data-section="market"]').click();
  await expect(page.locator("#market-data-table tr.market-row").first()).toBeVisible();

  const [popup] = await Promise.all([
    page.waitForEvent("popup"),
    page.locator("#market-data-table tr.market-row .market-link.external").first().click()
  ]);
  await expect(popup).toHaveURL(/dexscreener\.com/);
  await expect(page.locator("#market-detail-drawer")).not.toHaveClass(/open/);
});

test("shows fallback when row has no safe embed URL", async ({ page }) => {
  await page.goto("/static/index.html");
  await page.locator('.nav-link[data-section="market"]').click();
  await expect(page.locator("#market-data-table tr.market-row").nth(1)).toBeVisible();
  await page.locator("#market-data-table tr.market-row").nth(1).click();
  await expect(page.locator("#market-embed-fallback")).toHaveClass(/show/);
});

test("persists market section and selected pair across reload", async ({ page }) => {
  await page.goto("/static/index.html");
  await page.locator('.nav-link[data-section="market"]').click();
  await page.locator("#market-data-table tr.market-row").first().click();

  await expect(page).toHaveURL(/section=market/);
  await expect(page).toHaveURL(/pair_chain=solana/);

  await page.reload();
  await expect(page.locator('#market-section')).toBeVisible();
  await expect(page.locator("#market-detail-drawer")).toHaveClass(/open/);
});
