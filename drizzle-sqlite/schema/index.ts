/**
 * Drizzle ORM Schema for Sistema de Cadeia Dominial - SQLite Version
 *
 * This schema mirrors the Django models for the property chain tracking system
 * used to manage Indigenous lands (Terras Indigenas) in Brazil.
 *
 * SQLite-specific adaptations:
 * - Uses `text` instead of `varchar` (SQLite ignores length constraints)
 * - Uses `real` instead of `decimal` (SQLite has no true decimal type)
 * - Uses `integer({ mode: 'boolean' })` for boolean fields
 * - Stores dates/timestamps as ISO 8601 text strings
 * - No PostgreSQL-specific features (enums, arrays, etc.)
 */

// Export all tables and relations
export * from './tis';
export * from './pessoas';
export * from './cartorios';
export * from './imovel';
export * from './documentos';
export * from './lancamentos';
export * from './alteracoes';
export * from './relations';
