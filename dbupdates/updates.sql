ALTER TABLE `repairkawapp`.`user` 
CHANGE COLUMN `name` `name` VARCHAR(100) NULL DEFAULT NULL ;

ALTER TABLE `repairkawapp`.`user` 
ADD COLUMN `admin` TINYINT(1) NULL DEFAULT 0 AFTER `name`;

ALTER TABLE `repairkawapp`.`user` 
ADD COLUMN `seqid` INT NULL DEFAULT 0 AFTER `admin`;

