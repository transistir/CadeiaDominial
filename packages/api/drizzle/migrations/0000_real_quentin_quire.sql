CREATE TABLE `cri` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`nome` text NOT NULL,
	`cns_codigo` text,
	`cidade` text,
	`uf` text,
	`endereco` text,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	`updated_at` text DEFAULT (current_timestamp) NOT NULL,
	`deleted_at` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `uq_cri_cns_codigo_active` ON `cri` (`cns_codigo`) WHERE "cri"."cns_codigo" IS NOT NULL AND "cri"."deleted_at" IS NULL;--> statement-breakpoint
CREATE TABLE `v2_user` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`email` text NOT NULL,
	`nome` text NOT NULL,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	`updated_at` text DEFAULT (current_timestamp) NOT NULL,
	`deleted_at` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `uq_user_email_active` ON `v2_user` (`email`) WHERE "v2_user"."deleted_at" IS NULL;--> statement-breakpoint
CREATE TABLE `pessoa` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`nome` text NOT NULL,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	`updated_at` text DEFAULT (current_timestamp) NOT NULL,
	`deleted_at` text
);
--> statement-breakpoint
CREATE TABLE `imovel` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`nome` text NOT NULL,
	`observacoes` text,
	`data_cadastro` text,
	`cri_id` integer NOT NULL,
	`proprietario_id` integer,
	`arquivado` integer DEFAULT false NOT NULL,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	`updated_at` text DEFAULT (current_timestamp) NOT NULL,
	`deleted_at` text,
	`delete_operation_id` integer,
	FOREIGN KEY (`cri_id`) REFERENCES `cri`(`id`) ON UPDATE no action ON DELETE restrict,
	FOREIGN KEY (`proprietario_id`) REFERENCES `pessoa`(`id`) ON UPDATE no action ON DELETE set null,
	CONSTRAINT "imovel_arquivado_check" CHECK("imovel"."arquivado" IN (0, 1))
);
--> statement-breakpoint
CREATE TABLE `imovel_documento` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`imovel_id` integer NOT NULL,
	`documento_id` integer NOT NULL,
	`is_documento_atual` integer DEFAULT false NOT NULL,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	`deleted_at` text,
	`delete_operation_id` integer,
	`create_operation_id` integer,
	FOREIGN KEY (`imovel_id`) REFERENCES `imovel`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`documento_id`) REFERENCES `documento`(`id`) ON UPDATE no action ON DELETE restrict,
	CONSTRAINT "imovel_documento_is_documento_atual_check" CHECK("imovel_documento"."is_documento_atual" IN (0, 1))
);
--> statement-breakpoint
CREATE UNIQUE INDEX `uq_imovel_documento_pair_active` ON `imovel_documento` (`imovel_id`,`documento_id`) WHERE "imovel_documento"."deleted_at" IS NULL;--> statement-breakpoint
CREATE UNIQUE INDEX `uq_imovel_documento_atual_active` ON `imovel_documento` (`imovel_id`) WHERE "imovel_documento"."is_documento_atual" = 1 AND "imovel_documento"."deleted_at" IS NULL;--> statement-breakpoint
CREATE TABLE `documento` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`tipo` text NOT NULL,
	`numero` text NOT NULL,
	`numero_raw` text,
	`data` text,
	`livro` text,
	`folha` text,
	`data_cadastro` text,
	`cri_id` integer NOT NULL,
	`outorgante_nome` text,
	`outorgado_nome` text,
	`endereco` text,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	`deleted_at` text,
	`delete_operation_id` integer,
	`create_operation_id` integer,
	FOREIGN KEY (`cri_id`) REFERENCES `cri`(`id`) ON UPDATE no action ON DELETE restrict
);
--> statement-breakpoint
CREATE UNIQUE INDEX `uq_documento_cri_tipo_numero` ON `documento` (`cri_id`,`tipo`,`numero`);--> statement-breakpoint
CREATE TABLE `lancamento_tipo` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`tipo` text NOT NULL,
	`nome` text NOT NULL,
	`requer_detalhes` integer DEFAULT false NOT NULL,
	`requer_transmissao` integer DEFAULT false NOT NULL,
	`requer_cartorio_origem` integer DEFAULT false NOT NULL,
	`requer_data_origem` integer DEFAULT false NOT NULL,
	`requer_descricao` integer DEFAULT false NOT NULL,
	`requer_folha_origem` integer DEFAULT false NOT NULL,
	`requer_forma` integer DEFAULT false NOT NULL,
	`requer_livro_origem` integer DEFAULT false NOT NULL,
	`requer_observacao` integer DEFAULT false NOT NULL,
	`requer_titulo` integer DEFAULT false NOT NULL
);
--> statement-breakpoint
CREATE TABLE `lancamento` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`data` text,
	`valor_transacao_centavos` integer,
	`area_centiares` integer,
	`detalhes` text,
	`observacoes` text,
	`data_cadastro` text,
	`documento_id` integer,
	`tipo_id` integer NOT NULL,
	`descricao` text,
	`forma` text,
	`titulo` text,
	`numero_lancamento` integer,
	`cartorio_transmissao_nome` text,
	`livro_transmissao` text,
	`folha_transmissao` text,
	`data_transmissao` text,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	`deleted_at` text,
	`delete_operation_id` integer,
	FOREIGN KEY (`documento_id`) REFERENCES `documento`(`id`) ON UPDATE no action ON DELETE set null,
	FOREIGN KEY (`tipo_id`) REFERENCES `lancamento_tipo`(`id`) ON UPDATE no action ON DELETE restrict,
	CONSTRAINT "lancamento_numero_lancamento_positivo" CHECK("lancamento"."numero_lancamento" IS NULL OR "lancamento"."numero_lancamento" > 0)
);
--> statement-breakpoint
CREATE UNIQUE INDEX `uq_lancamento_documento_numero` ON `lancamento` (`documento_id`,`numero_lancamento`) WHERE "lancamento"."numero_lancamento" IS NOT NULL;--> statement-breakpoint
CREATE TABLE `lancamento_pessoa` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`papel` text NOT NULL,
	`nome_verbatim` text NOT NULL,
	`lancamento_id` integer NOT NULL,
	`pessoa_id` integer,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	`deleted_at` text,
	FOREIGN KEY (`lancamento_id`) REFERENCES `lancamento`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`pessoa_id`) REFERENCES `pessoa`(`id`) ON UPDATE no action ON DELETE set null
);
--> statement-breakpoint
CREATE TABLE `origem` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`lancamento_id` integer NOT NULL,
	`cri_id` integer NOT NULL,
	`documento_id` integer,
	`indice` integer NOT NULL,
	`tipo` text NOT NULL,
	`numero` text,
	`numero_raw` text,
	`livro` text,
	`folha` text,
	`data` text,
	`observacoes` text,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	FOREIGN KEY (`lancamento_id`) REFERENCES `lancamento`(`id`) ON UPDATE no action ON DELETE restrict,
	FOREIGN KEY (`cri_id`) REFERENCES `cri`(`id`) ON UPDATE no action ON DELETE restrict,
	FOREIGN KEY (`documento_id`) REFERENCES `documento`(`id`) ON UPDATE no action ON DELETE set null,
	CONSTRAINT "origem_indice_nao_negativo" CHECK("origem"."indice" >= 0)
);
--> statement-breakpoint
CREATE UNIQUE INDEX `uq_origem_lancamento_indice` ON `origem` (`lancamento_id`,`indice`);--> statement-breakpoint
CREATE TABLE `origem_fim_cadeia` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`origem_id` integer NOT NULL,
	`tipo_fim_cadeia` text,
	`classificacao_fim_cadeia` text,
	`especificacao_fim_cadeia` text,
	`sigla_patrimonio_publico` text,
	FOREIGN KEY (`origem_id`) REFERENCES `origem`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE UNIQUE INDEX `origem_fim_cadeia_origem_id_unique` ON `origem_fim_cadeia` (`origem_id`);--> statement-breakpoint
CREATE UNIQUE INDEX `uq_origem_fim_cadeia_origem` ON `origem_fim_cadeia` (`origem_id`);--> statement-breakpoint
CREATE TABLE `anotacao_versao` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`imovel_documento_id` integer NOT NULL,
	`autor_original_id` integer NOT NULL,
	`versao` integer NOT NULL,
	`texto` text NOT NULL,
	`is_current` integer DEFAULT false NOT NULL,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	`deleted_at` text,
	`created_by_id` integer,
	`operation_id` integer,
	FOREIGN KEY (`imovel_documento_id`) REFERENCES `imovel_documento`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`autor_original_id`) REFERENCES `v2_user`(`id`) ON UPDATE no action ON DELETE restrict,
	FOREIGN KEY (`created_by_id`) REFERENCES `v2_user`(`id`) ON UPDATE no action ON DELETE set null,
	CONSTRAINT "anotacao_versao_is_current_check" CHECK("anotacao_versao"."is_current" IN (0, 1)),
	CONSTRAINT "anotacao_versao_versao_positivo" CHECK("anotacao_versao"."versao" > 0)
);
--> statement-breakpoint
CREATE UNIQUE INDEX `uq_anotacao_versao_imovel_documento_current` ON `anotacao_versao` (`imovel_documento_id`) WHERE "anotacao_versao"."is_current" = 1 AND "anotacao_versao"."deleted_at" IS NULL;--> statement-breakpoint
CREATE TABLE `lancamento_move_event` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`lancamento_id` integer NOT NULL,
	`from_documento_id` integer,
	`to_documento_id` integer,
	`reason` text NOT NULL,
	`moved_by_id` integer,
	`moved_at` text NOT NULL,
	`audit_log_id` integer,
	FOREIGN KEY (`lancamento_id`) REFERENCES `lancamento`(`id`) ON UPDATE no action ON DELETE restrict,
	FOREIGN KEY (`from_documento_id`) REFERENCES `documento`(`id`) ON UPDATE no action ON DELETE set null,
	FOREIGN KEY (`to_documento_id`) REFERENCES `documento`(`id`) ON UPDATE no action ON DELETE set null,
	FOREIGN KEY (`moved_by_id`) REFERENCES `v2_user`(`id`) ON UPDATE no action ON DELETE set null,
	CONSTRAINT "lancamento_move_event_reason_nao_vazio" CHECK(length("lancamento_move_event"."reason") > 0)
);
--> statement-breakpoint
CREATE INDEX `idx_lancamento_move_event_lancamento_moved_at` ON `lancamento_move_event` (`lancamento_id`,`moved_at`,`id`);--> statement-breakpoint
CREATE TABLE `audit_log` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`operation_id` text NOT NULL,
	`action` text NOT NULL,
	`entity_type` text NOT NULL,
	`entity_id` integer NOT NULL,
	`payload_json` text,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	`actor_id` integer,
	FOREIGN KEY (`actor_id`) REFERENCES `v2_user`(`id`) ON UPDATE no action ON DELETE set null
);
--> statement-breakpoint
CREATE TABLE `tis` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`codigo` text NOT NULL,
	`etnia` text NOT NULL,
	`data_cadastro` text NOT NULL,
	`terra_referencia_id` integer,
	`area_centiares` integer,
	`estado` text,
	`nome` text,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	`updated_at` text DEFAULT (current_timestamp) NOT NULL,
	FOREIGN KEY (`terra_referencia_id`) REFERENCES `terra_indigena_referencia`(`id`) ON UPDATE no action ON DELETE restrict
);
--> statement-breakpoint
CREATE TABLE `tis_imovel` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`tis_id` integer NOT NULL,
	`imovel_id` integer NOT NULL,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	FOREIGN KEY (`tis_id`) REFERENCES `tis`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`imovel_id`) REFERENCES `imovel`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE UNIQUE INDEX `uq_tis_imovel_tis_imovel` ON `tis_imovel` (`tis_id`,`imovel_id`);--> statement-breakpoint
CREATE TABLE `terra_indigena_referencia` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`codigo` text NOT NULL,
	`nome` text NOT NULL,
	`etnia` text,
	`estado` text,
	`municipio` text,
	`area_ha_centiares` integer,
	`fase` text,
	`modalidade` text,
	`coordenacao_regional` text,
	`data_regularizada` text,
	`data_homologada` text,
	`data_declarada` text,
	`data_delimitada` text,
	`data_em_estudo` text,
	`created_at` text DEFAULT (current_timestamp) NOT NULL,
	`updated_at` text DEFAULT (current_timestamp) NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `uq_terra_indigena_referencia_codigo` ON `terra_indigena_referencia` (`codigo`);--> statement-breakpoint
CREATE VIEW `v_documento_orfao` AS 
  SELECT d.id, d.tipo, d.numero, d.cri_id
  FROM documento d
  WHERE d.deleted_at IS NULL
    AND NOT EXISTS (
      SELECT 1 FROM imovel_documento id_
      WHERE id_.documento_id = d.id
        AND id_.deleted_at IS NULL
    )
;--> statement-breakpoint
CREATE VIEW `v_lancamento_current_location` AS 
  SELECT
    inner_q.lancamento_id AS lancamento_id,
    inner_q.current_documento_id AS current_documento_id
  FROM (
    SELECT
      l.id AS lancamento_id,
      COALESCE(
        (SELECT me.to_documento_id
         FROM lancamento_move_event me
         WHERE me.lancamento_id = l.id
         ORDER BY me.moved_at DESC, me.id DESC
         LIMIT 1),
        l.documento_id
      ) AS current_documento_id
    FROM lancamento l
    WHERE l.deleted_at IS NULL
  ) inner_q
  INNER JOIN documento d ON d.id = inner_q.current_documento_id
  WHERE d.deleted_at IS NULL
;