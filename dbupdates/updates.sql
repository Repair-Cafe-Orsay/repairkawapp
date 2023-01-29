ALTER TABLE `repairkawapp`.`user` 
CHANGE COLUMN `name` `name` VARCHAR(100) NULL DEFAULT NULL ;

ALTER TABLE `repairkawapp`.`user` 
ADD COLUMN `admin` TINYINT(1) NULL DEFAULT 0 AFTER `name`;

ALTER TABLE `repairkawapp`.`user` 
ADD COLUMN `seqid` INT NULL DEFAULT 0 AFTER `admin`;




CREATE TABLE `repairkawapp`.`repaircafe` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(45) NOT NULL,
  PRIMARY KEY (`id`))
  ADD UNIQUE INDEX `name_UNIQUE` (`name` ASC) VISIBLE;
;
INSERT INTO `repairkawapp`.`repaircafe` (`name`) VALUES ('Repair Café Orsay');

ALTER TABLE `repairkawapp`.`repair`
ADD COLUMN `repaircafe_id` INT(11) NOT NULL DEFAULT 1 AFTER `location`;

ALTER TABLE `repairkawapp`.`repair`
ADD INDEX `repair_ibfk_6_idx` (`repaircafe_id` ASC) VISIBLE;
;
ALTER TABLE `repairkawapp`.`repair`
ADD CONSTRAINT `repair_ibfk_6`
  FOREIGN KEY (`repaircafe_id`)
  REFERENCES `repairkawapp`.`repaircafe` (`id`)
  ON DELETE NO ACTION
  ON UPDATE NO ACTION;

CREATE TABLE `repairkawapp`.`association_repaircafe_user` (
  `repaircafe_id` INT NOT NULL,
  `user_id` INT NOT NULL,
  INDEX `ibfk_1_idx` (`user_id` ASC) VISIBLE,
  INDEX `ibfk_2_idx` (`repaircafe_id` ASC) VISIBLE,
  CONSTRAINT `ibfk_1`
    FOREIGN KEY (`user_id`)
    REFERENCES `repairkawapp`.`user` (`id`)
    ON DELETE CASCADE
    ON UPDATE NO ACTION,
  CONSTRAINT `ibfk_2`
    FOREIGN KEY (`repaircafe_id`)
    REFERENCES `repairkawapp`.`repaircafe` (`id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION);

INSERT INTO `repairkawapp`.`association_repaircafe_user` (`repaircafe_id`,`user_id`)
    VALUES (1,1),
     (1,2),
     (1,3),
     (1,4),
     (1,5),
     (1,6),
     (1,7),
     (1,8),
     (1,9),
     (1,10),
     (1,11),
     (1,12),
     (1,13),
     (1,14),
     (1,15),
     (1,16),
     (1,17),
     (1,18),
     (1,19),
     (1,20);

INSERT INTO `repairkawapp`.`repaircafe` (`name`) VALUES ('Répare Café Palaiseau');
