/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Hàm sửa dữ liệu THUẦN: chỉ sửa trên một bản FamilyOrganizerDB đã đọc, không đọc/ghi SQLite.
// Dùng chung cho endpoint thường (FamilyDB.save*/delete*) và apply đề xuất của trợ lý
// (FamilyDB.applyBatch) để hai đường ghi không lệch nhau. File không có side effect khi import.

import crypto from "crypto";
import type { FamilyOrganizerDB, ShoppingItem } from "../src/types.js";

/** ID mới: tiền tố + thời gian + hậu tố ngẫu nhiên — ghi nhiều bản ghi liền nhau không trùng. */
export function newId(prefix: string): string {
  return `${prefix}_${Date.now()}_${crypto.randomBytes(6).toString("hex")}`;
}

const MAX_ACTIVITY_LOGS = 300;

function mutateLogActivity(db: FamilyOrganizerDB, userId: string, username: string, action: string, details: string): void {
  db.activityLogs.unshift({
    id: newId("log"),
    userId,
    username,
    action,
    details,
    createdAt: new Date().toISOString()
  });
  // Cap logs to keep it lightweight on Raspberry Pi 5
  if (db.activityLogs.length > MAX_ACTIVITY_LOGS) {
    db.activityLogs = db.activityLogs.slice(0, MAX_ACTIVITY_LOGS);
  }
}

/** Thêm một món đi chợ vào `db` (chưa ghi) + nhật ký. */
export function mutateAddShopping(
  db: FamilyOrganizerDB,
  data: Partial<ShoppingItem>,
  userId: string,
  username: string
): ShoppingItem {
  const now = new Date().toISOString();
  const newItem: ShoppingItem = {
    id: newId("shop"),
    name: (data.name || "Món đồ").trim(),
    quantity: data.quantity?.trim() || "",
    note: data.note?.trim() || "",
    cat: data.cat?.trim() || "",
    isPurchased: false,
    creatorId: userId,
    purchasedById: null,
    createdAt: now,
    updatedAt: now
  };
  db.shoppingItems.unshift(newItem);
  mutateLogActivity(db, userId, username, "Thêm đồ đi chợ", `Đã thêm "${newItem.name}" vào danh sách mua sắm.`);
  return newItem;
}

/** ĐẶT trạng thái đã mua (không lật). Bằng trạng thái hiện tại → không đổi gì, changed=false. */
export function mutateSetShoppingPurchased(
  db: FamilyOrganizerDB,
  id: string,
  purchased: boolean,
  userId: string
): { item: ShoppingItem; changed: boolean } {
  const item = db.shoppingItems.find(i => i.id === id);
  if (!item) throw new Error("Món đồ không tồn tại");
  if (Boolean(item.isPurchased) === purchased) return { item, changed: false };
  item.isPurchased = purchased;
  item.purchasedById = purchased ? userId : null;
  item.updatedAt = new Date().toISOString();
  return { item, changed: true };
}

/** Xoá một món + nhật ký. Không tồn tại → null (giống DELETE /api/shopping/:id). */
export function mutateDeleteShopping(
  db: FamilyOrganizerDB,
  id: string,
  userId: string,
  username: string
): ShoppingItem | null {
  const idx = db.shoppingItems.findIndex(i => i.id === id);
  if (idx === -1) return null;
  const [removed] = db.shoppingItems.splice(idx, 1);
  mutateLogActivity(db, userId, username, "Xóa đồ đi chợ", `Đã xóa "${removed.name}" khỏi danh sách mua sắm.`);
  return removed;
}

