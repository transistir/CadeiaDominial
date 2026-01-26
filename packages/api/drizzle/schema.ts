import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const healthChecks = sqliteTable("health_checks", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  status: text("status").notNull(),
  checkedAt: integer("checked_at", { mode: "timestamp" }).notNull()
});
