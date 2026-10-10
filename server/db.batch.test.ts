/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// FamilyDB mở data/family.db theo process.cwd() ngay khi import → chạy trong thư mục tạm.
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import fs from "fs";
import os from "os";
import path from "path";

const prevCwd = process.cwd();
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "fo-db-batch-"));
let FamilyDB: typeof import("./db.js").FamilyDB;
let db: typeof import("./db.js");

beforeAll(async () => {
  process.chdir(tmp);
  db = await import("./db.js");
  FamilyDB = db.FamilyDB;
});

afterAll(() => {
  process.chdir(prevCwd);
  fs.rmSync(tmp, { recursive: true, force: true });
});

describe("ID mới không trùng khi ghi liền nhau (C1)", () => {
  it("50 món thêm liên tiếp có 50 id khác nhau", () => {
    const ids = new Set<string>();
    for (let i = 0; i < 50; i++) ids.add(FamilyDB.saveShoppingItem({ name: `món ${i}` }, "user_admin", "admin").id);
    expect(ids.size).toBe(50);
    FamilyDB.clearAllShopping("user_admin", "admin");
  });

  it("newId có tiền tố + thời gian + hậu tố ngẫu nhiên", () => {
    expect(db.newId("shop")).toMatch(/^shop_\d+_[a-f0-9]{12}$/);
  });
});

describe("FamilyDB.applyBatch", () => {
  it("30 món trong một batch → đúng 30 dòng, id khác nhau, nhật ký có ghi", () => {
    const before = FamilyDB.getShoppingItems().length;
    const items = FamilyDB.applyBatch((d) =>
      Array.from({ length: 30 }, (_, i) => db.mutateAddShopping(d, { name: `trứng ${i}` }, "user_admin", "admin")),
    );
    const all = FamilyDB.getShoppingItems();
    expect(all.length).toBe(before + 30);
    expect(new Set(items.map((i) => i.id)).size).toBe(30);
    expect(FamilyDB.getActivityLogs().some((l) => l.details.includes("trứng 29"))).toBe(true);
  });

  it("hàm ném lỗi → không ghi gì", () => {
    const before = FamilyDB.getShoppingItems().length;
    expect(() =>
      FamilyDB.applyBatch((d) => {
        db.mutateAddShopping(d, { name: "sữa" }, "user_admin", "admin");
        throw new Error("hỏng giữa chừng");
      }),
    ).toThrow("hỏng giữa chừng");
    expect(FamilyDB.getShoppingItems().length).toBe(before);
  });

  it("ghi SQLite thất bại → ném lỗi (không nuốt) và không còn dòng nào", () => {
    const before = FamilyDB.getShoppingItems().length;
    expect(() =>
      FamilyDB.applyBatch((d) => {
        const item = db.mutateAddShopping(d, { name: "hỏng" }, "user_admin", "admin");
        (item as unknown as { self: unknown }).self = item; // vòng tham chiếu → JSON.stringify ném trong transaction
      }),
    ).toThrow();
    expect(FamilyDB.getShoppingItems().length).toBe(before);
  });
});

describe("mutate đi chợ", () => {
  it("set purchased: đặt giá trị (không lật); bằng trạng thái hiện tại → changed=false", () => {
    const item = FamilyDB.saveShoppingItem({ name: "rau" }, "user_admin", "admin");
    const r1 = FamilyDB.applyBatch((d) => db.mutateSetShoppingPurchased(d, item.id, true, "kid1"));
    expect(r1.changed).toBe(true);
    expect(r1.item.isPurchased).toBe(true);
    expect(r1.item.purchasedById).toBe("kid1");
    const r2 = FamilyDB.applyBatch((d) => db.mutateSetShoppingPurchased(d, item.id, true, "kid1"));
    expect(r2.changed).toBe(false);
    expect(FamilyDB.getShoppingItem(item.id)?.isPurchased).toBe(true);
    const r3 = FamilyDB.applyBatch((d) => db.mutateSetShoppingPurchased(d, item.id, false, "kid1"));
    expect(r3.item.isPurchased).toBe(false);
    expect(r3.item.purchasedById).toBeNull();
  });

  it("set purchased món không tồn tại → ném lỗi", () => {
    expect(() => FamilyDB.applyBatch((d) => db.mutateSetShoppingPurchased(d, "shop_x", true, "u"))).toThrow();
  });

  it("delete: xoá món + ghi nhật ký; món không tồn tại → null", () => {
    const item = FamilyDB.saveShoppingItem({ name: "cá" }, "user_admin", "admin");
    const removed = FamilyDB.applyBatch((d) => db.mutateDeleteShopping(d, item.id, "user_admin", "admin"));
    expect(removed?.name).toBe("cá");
    expect(FamilyDB.getShoppingItem(item.id)).toBeUndefined();
    expect(FamilyDB.applyBatch((d) => db.mutateDeleteShopping(d, item.id, "user_admin", "admin"))).toBeNull();
  });

  it("endpoint cũ giữ hành vi: saveShoppingItem tạo món + log, deleteShoppingItem xoá", () => {
    const item = FamilyDB.saveShoppingItem({ name: "  thịt  ", quantity: " 1kg " }, "user_admin", "admin");
    expect(item).toMatchObject({ name: "thịt", quantity: "1kg", isPurchased: false, creatorId: "user_admin" });
    expect(FamilyDB.getActivityLogs()[0].details).toContain('"thịt"');
    FamilyDB.deleteShoppingItem(item.id, "user_admin", "admin");
    expect(FamilyDB.getShoppingItem(item.id)).toBeUndefined();
    expect(FamilyDB.getActivityLogs()[0].action).toBe("Xóa đồ đi chợ");
  });
});
