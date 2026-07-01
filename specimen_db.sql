
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `page_content`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `page_content` (
  `id` int NOT NULL AUTO_INCREMENT,
  `page` varchar(30) NOT NULL COMMENT '页面标识: landing, about, site',
  `section` varchar(50) NOT NULL COMMENT '区块标识',
  `content` text COMMENT '内容文本',
  `updated_by` varchar(50) DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_page_section` (`page`,`section`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `specimen`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `specimen` (
  `id` int NOT NULL AUTO_INCREMENT,
  `category_id` int NOT NULL COMMENT '大类ID，外键，关联 specimen_category.id',
  `specimen_number` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '标本编号',
  `chinese_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '中文名',
  `latin_name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '拉丁名',
  `alias` text COLLATE utf8mb4_unicode_ci COMMENT '别名',
  `phylum` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '门',
  `class_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '纲',
  `order` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '目',
  `family` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '科',
  `genus` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '属',
  `species` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '种',
  `collector` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '采集人',
  `collect_time` datetime NOT NULL COMMENT '采集时间',
  `collect_location` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '采集地点',
  `longitude` decimal(10,6) DEFAULT NULL,
  `latitude` decimal(10,6) DEFAULT NULL,
  `appraiser` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '鉴定人',
  `appraisal_time` datetime DEFAULT NULL COMMENT '鉴定时间',
  `other_info` json DEFAULT NULL COMMENT '其他信息，可存储 JSON',
  `created_by` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '创建人',
  `updated_by` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '修改人',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  PRIMARY KEY (`id`),
  KEY `fk_specimen_category` (`category_id`),
  KEY `ix_specimen_latin_name` (`latin_name`),
  CONSTRAINT `fk_specimen_category` FOREIGN KEY (`category_id`) REFERENCES `specimen_category` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=33 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标本信息表';
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `specimen_category`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `specimen_category` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '类别名称，如鱼类、浮游植物',
  `code` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci COMMENT '可选说明',
  `created_by` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '创建人',
  `updated_by` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '修改人',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  `image` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '大类封面图片路径',
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标本大类表';
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `specimen_image`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `specimen_image` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '图片ID',
  `specimen_id` int NOT NULL COMMENT '外键，关联标本表 specimen.id',
  `image_path` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '图片路径',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
  `sort_order` int DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `fk_specimen_image` (`specimen_id`),
  CONSTRAINT `fk_specimen_image` FOREIGN KEY (`specimen_id`) REFERENCES `specimen` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=39 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标本图片表';
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户名',
  `password_hash` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '密码哈希值',
  `role` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'user' COMMENT '角色：superadmin/超级管理员，admin/管理员，user/普通用户',
  `is_admin` tinyint(1) GENERATED ALWAYS AS ((`role` in (_utf8mb4'superadmin',_utf8mb4'admin'))) VIRTUAL COMMENT '是否为管理员（虚拟字段）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

