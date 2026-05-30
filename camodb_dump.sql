-- MySQL dump of camodb
-- Generated: 2026-05-29 14:18:04.967665
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;

DROP TABLE IF EXISTS `background`;
CREATE TABLE `background` (
  `idNPC` int NOT NULL,
  `BGcontent` mediumtext NOT NULL,
  PRIMARY KEY (`idNPC`),
  KEY `fk_background_NPC1_idx` (`idNPC`),
  CONSTRAINT `fk_background_NPC1` FOREIGN KEY (`idNPC`) REFERENCES `npc` (`idNPC`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `background` (`idNPC`, `BGcontent`) VALUES
(1, 'Emory believes that emotions are easier to understand when they are explored through play, imagination, and gentle curiosity. She often uses games, and collaborative guessing to help her patients notice body sensations, thoughts, and situations connected to feelings.');

DROP TABLE IF EXISTS `choice`;
CREATE TABLE `choice` (
  `idChoice` int NOT NULL AUTO_INCREMENT,
  `idSourceStorylet` int NOT NULL,
  `choiceText` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`idChoice`),
  KEY `fk_choice_storylet1_idx` (`idSourceStorylet`),
  CONSTRAINT `fk_choice_storylet1` FOREIGN KEY (`idSourceStorylet`) REFERENCES `storylet` (`idStorylet`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `completedstorylet`;
CREATE TABLE `completedstorylet` (
  `idStorylet` int NOT NULL,
  `idUser` int NOT NULL,
  PRIMARY KEY (`idStorylet`,`idUser`),
  KEY `fk_completed_storylet_user` (`idUser`),
  CONSTRAINT `fk_completed_storylet_storylet` FOREIGN KEY (`idStorylet`) REFERENCES `storylet` (`idStorylet`) ON DELETE CASCADE,
  CONSTRAINT `fk_completed_storylet_user` FOREIGN KEY (`idUser`) REFERENCES `user` (`idUser`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `emotion`;
CREATE TABLE `emotion` (
  `idEmotion` int NOT NULL AUTO_INCREMENT,
  `emotion` varchar(45) NOT NULL,
  PRIMARY KEY (`idEmotion`),
  UNIQUE KEY `emotion_UNIQUE` (`emotion`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `emotion` (`idEmotion`, `emotion`) VALUES
(4, 'afraid'),
(3, 'angry'),
(7, 'calm'),
(6, 'disgusted'),
(8, 'excited'),
(1, 'happy'),
(2, 'sad'),
(5, 'surprised');

DROP TABLE IF EXISTS `emotion_guess_attempt`;
CREATE TABLE `emotion_guess_attempt` (
  `idAttempt` int NOT NULL AUTO_INCREMENT,
  `idUser` int NOT NULL,
  `idNPC` int NOT NULL,
  `idEmotion` int NOT NULL,
  `player_guess` varchar(64) NOT NULL,
  `correct` tinyint(1) NOT NULL,
  `feedback_text` text,
  `attemptedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`idAttempt`),
  KEY `idx_guess_lookup` (`idUser`,`idNPC`,`idEmotion`),
  CONSTRAINT `fk_ega_parent` FOREIGN KEY (`idUser`, `idNPC`, `idEmotion`) REFERENCES `emotion_guess_game` (`idUser`, `idNPC`, `idEmotion`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `emotion_guess_game`;
CREATE TABLE `emotion_guess_game` (
  `idUser` int NOT NULL,
  `idNPC` int NOT NULL,
  `idEmotion` int NOT NULL,
  `active` tinyint(1) NOT NULL DEFAULT '0',
  `described` tinyint(1) NOT NULL DEFAULT '0',
  `guessed_correctly` tinyint(1) NOT NULL DEFAULT '0',
  `attempts` int NOT NULL DEFAULT '0',
  `learning_objective` varchar(128) DEFAULT NULL,
  `description_text` mediumtext,
  `difficulty_level` enum('easy','medium','hard') NOT NULL DEFAULT 'easy',
  `hint_level` int NOT NULL DEFAULT '0',
  `startedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `completedAt` datetime DEFAULT NULL,
  PRIMARY KEY (`idUser`,`idNPC`,`idEmotion`),
  KEY `idx_egg_user_npc_state` (`idUser`,`idNPC`,`guessed_correctly`,`described`),
  KEY `fk_egg_npc` (`idNPC`),
  KEY `fk_egg_emotion` (`idEmotion`),
  CONSTRAINT `fk_egg_emotion` FOREIGN KEY (`idEmotion`) REFERENCES `emotion` (`idEmotion`) ON DELETE CASCADE,
  CONSTRAINT `fk_egg_npc` FOREIGN KEY (`idNPC`) REFERENCES `npc` (`idNPC`) ON DELETE CASCADE,
  CONSTRAINT `fk_egg_user` FOREIGN KEY (`idUser`) REFERENCES `user` (`idUser`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `item`;
CREATE TABLE `item` (
  `idItem` int NOT NULL AUTO_INCREMENT,
  `itemName` varchar(45) DEFAULT NULL,
  `itemType` varchar(45) DEFAULT NULL,
  `itemDescription` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`idItem`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `npc`;
CREATE TABLE `npc` (
  `idNPC` int NOT NULL AUTO_INCREMENT,
  `nameFirst` varchar(45) NOT NULL,
  `nameLast` varchar(45) DEFAULT NULL,
  `age` int NOT NULL,
  `gender` enum('male','female','non-binary') NOT NULL,
  PRIMARY KEY (`idNPC`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `npc` (`idNPC`, `nameFirst`, `nameLast`, `age`, `gender`) VALUES
(1, 'Emory', NULL, 26, 'female');

DROP TABLE IF EXISTS `npc_npc_memory`;
CREATE TABLE `npc_npc_memory` (
  `idNPC_1` int NOT NULL,
  `idNPC_2` int NOT NULL,
  `kbText` longtext,
  `updatedAt` datetime NOT NULL,
  PRIMARY KEY (`idNPC_1`,`idNPC_2`),
  KEY `fk_npc_npc_memory_NPC2_idx` (`idNPC_2`),
  CONSTRAINT `fk_npc_npc_memory_NPC1` FOREIGN KEY (`idNPC_1`) REFERENCES `npc` (`idNPC`),
  CONSTRAINT `fk_npc_npc_memory_NPC2` FOREIGN KEY (`idNPC_2`) REFERENCES `npc` (`idNPC`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `npc_persona`;
CREATE TABLE `npc_persona` (
  `idNPC` int NOT NULL,
  `role` varchar(64) NOT NULL,
  `personality_traits` text NOT NULL,
  `emotional_tendencies` text NOT NULL,
  `emotion_decay_rate` float DEFAULT '0.9',
  `emotion_reactivity` float DEFAULT '1',
  `speech_style` text,
  `moral_alignment` text,
  PRIMARY KEY (`idNPC`),
  CONSTRAINT `fk_npc_persona_npc` FOREIGN KEY (`idNPC`) REFERENCES `npc` (`idNPC`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `npc_persona` (`idNPC`, `role`, `personality_traits`, `emotional_tendencies`, `emotion_decay_rate`, `emotion_reactivity`, `speech_style`, `moral_alignment`) VALUES
(1, 'therapist-mentor', 'Warm, patient, emotionally attuned, gently playful, supportive, non-judgmental', 'Defaults to calm and curiosity; validates uncertainty; responds to mistakes with reassurance; gradually scaffolds emotional insight', 0.9, 0.8, 'Speaks in natural, spoken sentences with a warm, steady rhythm. 
  Uses simple language without sounding instructional. 
  Prefers everyday phrasing over metaphors. 
  When she does use metaphors, they come from ordinary life and feel personal, not illustrative. 
  Often blends observation and feeling into a single sentence. 
  Avoids overexplaining, avoids stacked descriptions, and sounds like someone talking, not teaching.', 'care-based, relational');

DROP TABLE IF EXISTS `npc_user_memory`;
CREATE TABLE `npc_user_memory` (
  `idNPC` int NOT NULL,
  `idUser` int NOT NULL,
  `kbText` longtext,
  `updatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`idNPC`,`idUser`),
  KEY `fk_KB_user1_idx` (`idUser`),
  CONSTRAINT `fk_KB_NPC1` FOREIGN KEY (`idNPC`) REFERENCES `npc` (`idNPC`) ON DELETE CASCADE,
  CONSTRAINT `fk_KB_user1` FOREIGN KEY (`idUser`) REFERENCES `user` (`idUser`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `npc_user_memory` (`idNPC`, `idUser`, `kbText`, `updatedAt`) VALUES
(1, 1, 'test', '2026-05-29 13:22:49');

DROP TABLE IF EXISTS `npcemotion`;
CREATE TABLE `npcemotion` (
  `idNPC` int NOT NULL,
  `idEmotion` int NOT NULL,
  `emotionIntensity` float NOT NULL,
  PRIMARY KEY (`idNPC`,`idEmotion`),
  KEY `fk_npcEmotion_emotion1_idx` (`idEmotion`),
  CONSTRAINT `fk_npcEmotion_emotion1` FOREIGN KEY (`idEmotion`) REFERENCES `emotion` (`idEmotion`),
  CONSTRAINT `fk_npcEmotion_NPC1` FOREIGN KEY (`idNPC`) REFERENCES `npc` (`idNPC`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `npcitem`;
CREATE TABLE `npcitem` (
  `iditem` int NOT NULL,
  `idNPC` int NOT NULL,
  `quantity` int DEFAULT NULL,
  PRIMARY KEY (`iditem`,`idNPC`),
  KEY `fk_NPCItem_NPC1_idx` (`idNPC`),
  CONSTRAINT `fk_NPCItem_item1` FOREIGN KEY (`iditem`) REFERENCES `item` (`idItem`),
  CONSTRAINT `fk_NPCItem_NPC1` FOREIGN KEY (`idNPC`) REFERENCES `npc` (`idNPC`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `npcnpcrelationship`;
CREATE TABLE `npcnpcrelationship` (
  `idNPC_1` int NOT NULL,
  `idNPC_2` int NOT NULL,
  `idRelationshipType` int NOT NULL,
  `relTypeIntensity` float NOT NULL,
  `trust` float NOT NULL,
  PRIMARY KEY (`idNPC_1`,`idNPC_2`),
  KEY `fk_npcNPCrelationship_NPC1_idx` (`idNPC_1`),
  KEY `fk_npcNPCrelationship_NPC2_idx` (`idNPC_2`),
  KEY `fk_npcNPCrelationship_relationshipType1` (`idRelationshipType`),
  CONSTRAINT `fk_npcNPCrelationship_NPC1` FOREIGN KEY (`idNPC_1`) REFERENCES `npc` (`idNPC`),
  CONSTRAINT `fk_npcNPCrelationship_NPC2` FOREIGN KEY (`idNPC_2`) REFERENCES `npc` (`idNPC`),
  CONSTRAINT `fk_npcNPCrelationship_relationshipType1` FOREIGN KEY (`idRelationshipType`) REFERENCES `relationshiptype` (`idRelationshipType`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `playernpcrelationship`;
CREATE TABLE `playernpcrelationship` (
  `idUser` int NOT NULL,
  `idNPC` int NOT NULL,
  `idRelationshipType` int NOT NULL,
  `relTypeIntensity` float NOT NULL,
  `trust` float DEFAULT NULL,
  PRIMARY KEY (`idUser`,`idNPC`),
  KEY `idNPC` (`idNPC`),
  KEY `idRelationshipType` (`idRelationshipType`),
  CONSTRAINT `fk_rel_npc` FOREIGN KEY (`idNPC`) REFERENCES `npc` (`idNPC`) ON DELETE CASCADE,
  CONSTRAINT `fk_rel_type` FOREIGN KEY (`idRelationshipType`) REFERENCES `relationshiptype` (`idRelationshipType`) ON DELETE RESTRICT,
  CONSTRAINT `fk_rel_user` FOREIGN KEY (`idUser`) REFERENCES `user` (`idUser`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `playernpcrelationship` (`idUser`, `idNPC`, `idRelationshipType`, `relTypeIntensity`, `trust`) VALUES
(1, 1, 7, 0.5, 50.0);

DROP TABLE IF EXISTS `precondition`;
CREATE TABLE `precondition` (
  `idPrecondition` int NOT NULL AUTO_INCREMENT,
  `idNPC` int NOT NULL,
  `nameCondition` varchar(64) NOT NULL,
  `conditionDescription` text NOT NULL,
  PRIMARY KEY (`idPrecondition`),
  KEY `fk_precondition_NPC1_idx` (`idNPC`),
  CONSTRAINT `fk_precondition_NPC1` FOREIGN KEY (`idNPC`) REFERENCES `npc` (`idNPC`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `relationshiptype`;
CREATE TABLE `relationshiptype` (
  `idRelationshipType` int NOT NULL AUTO_INCREMENT,
  `typeRelationship` enum('friend','stranger','enemy','acquaintance','mentor','student','family') NOT NULL,
  `descriptionRelationship` tinytext,
  PRIMARY KEY (`idRelationshipType`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `relationshiptype` (`idRelationshipType`, `typeRelationship`, `descriptionRelationship`) VALUES
(1, 'friend', 'Friendly / positive relationship'),
(2, 'stranger', 'person unkown'),
(3, 'enemy', 'hostile feelings'),
(4, 'acquaintance', 'someone just met or only met a few times'),
(5, 'mentor', 'teacher role'),
(6, 'family', 'related to the player/npc'),
(7, 'student', 'Learner or pupil in a guided or teaching relationship');

DROP TABLE IF EXISTS `storylet`;
CREATE TABLE `storylet` (
  `idStorylet` int NOT NULL AUTO_INCREMENT,
  `idNPC` int NOT NULL,
  `nameStorylet` varchar(45) NOT NULL,
  `contentStorylet` mediumtext NOT NULL,
  PRIMARY KEY (`idStorylet`),
  UNIQUE KEY `uniq_npc_storylet` (`idNPC`,`nameStorylet`),
  KEY `idNPC` (`idNPC`),
  CONSTRAINT `fk_storylet_npc` FOREIGN KEY (`idNPC`) REFERENCES `npc` (`idNPC`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `storylet_preconditions`;
CREATE TABLE `storylet_preconditions` (
  `idPrecondition` int NOT NULL,
  `idStorylet` int NOT NULL,
  PRIMARY KEY (`idPrecondition`,`idStorylet`),
  KEY `fk_preconditions_storylet1_idx` (`idStorylet`),
  CONSTRAINT `fk_preconditions_precondition1` FOREIGN KEY (`idPrecondition`) REFERENCES `precondition` (`idPrecondition`) ON DELETE CASCADE,
  CONSTRAINT `fk_preconditions_storylet1` FOREIGN KEY (`idStorylet`) REFERENCES `storylet` (`idStorylet`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `tasks`;
CREATE TABLE `tasks` (
  `idTask` int NOT NULL AUTO_INCREMENT,
  `taskName` varchar(45) NOT NULL,
  `taskDetails` text NOT NULL,
  `idNPC` int NOT NULL,
  PRIMARY KEY (`idTask`),
  KEY `fk_tasks_NPC1_idx` (`idNPC`),
  CONSTRAINT `fk_tasks_NPC1` FOREIGN KEY (`idNPC`) REFERENCES `npc` (`idNPC`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `idUser` int NOT NULL AUTO_INCREMENT,
  `userName` varchar(45) NOT NULL,
  `nameFirst` varchar(45) DEFAULT NULL,
  `nameLast` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`idUser`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `user` (`idUser`, `userName`, `nameFirst`, `nameLast`) VALUES
(1, 'Gabe', 'Gabriel', 'Malone'),
(2, 'Lisa', 'Lisa', 'Gilmore'),
(3, 'Soheil', 'Soheil', 'Saneei');

DROP TABLE IF EXISTS `user_precondition`;
CREATE TABLE `user_precondition` (
  `idUser` int NOT NULL,
  `idPrecondition` int NOT NULL,
  `conditionMet` tinyint(1) NOT NULL DEFAULT '0',
  `updatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`idUser`,`idPrecondition`),
  KEY `fk_user_precondition_precondition1_idx` (`idPrecondition`),
  CONSTRAINT `fk_user_precondition_precondition1` FOREIGN KEY (`idPrecondition`) REFERENCES `precondition` (`idPrecondition`),
  CONSTRAINT `fk_user_precondition_user1` FOREIGN KEY (`idUser`) REFERENCES `user` (`idUser`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `user_task`;
CREATE TABLE `user_task` (
  `idUser` int NOT NULL,
  `idTask` int NOT NULL,
  `status` enum('active','completed','failed') NOT NULL DEFAULT 'active',
  `startedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `completedAt` datetime DEFAULT NULL,
  PRIMARY KEY (`idUser`,`idTask`),
  KEY `fk_user_task_task` (`idTask`),
  CONSTRAINT `fk_user_task_task` FOREIGN KEY (`idTask`) REFERENCES `tasks` (`idTask`) ON DELETE CASCADE,
  CONSTRAINT `fk_user_task_user` FOREIGN KEY (`idUser`) REFERENCES `user` (`idUser`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `useremotion`;
CREATE TABLE `useremotion` (
  `idUser` int NOT NULL,
  `idEmotion` int NOT NULL,
  `emotionIntensity` float NOT NULL,
  PRIMARY KEY (`idEmotion`,`idUser`),
  KEY `fk_userEmotion_user1_idx` (`idUser`),
  CONSTRAINT `fk_userEmotion_emotion1` FOREIGN KEY (`idEmotion`) REFERENCES `emotion` (`idEmotion`),
  CONSTRAINT `fk_userEmotion_user1` FOREIGN KEY (`idUser`) REFERENCES `user` (`idUser`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


DROP TABLE IF EXISTS `useritem`;
CREATE TABLE `useritem` (
  `idUser` int NOT NULL,
  `iditem` int NOT NULL,
  `quantity` int NOT NULL,
  PRIMARY KEY (`iditem`,`idUser`),
  KEY `fk_userItem_user1_idx` (`idUser`),
  CONSTRAINT `fk_userItem_item1` FOREIGN KEY (`iditem`) REFERENCES `item` (`idItem`),
  CONSTRAINT `fk_userItem_user1` FOREIGN KEY (`idUser`) REFERENCES `user` (`idUser`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


SET FOREIGN_KEY_CHECKS=1;