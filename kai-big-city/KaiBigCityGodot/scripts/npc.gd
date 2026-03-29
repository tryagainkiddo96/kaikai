extends Area3D

@export var npc_name := "Neighbor"
@export var message := "Hey Kai! Can you find my lunch bag?"
@export var quest_id := "missing_lunch"
@export var complete_message := "You found it! Thank you, Kai."
@export var reward_treats := 3

func _ready() -> void:
	add_to_group("npc")

func talk(player: Node = null) -> String:
	if player != null and player.has_meta(quest_id) and player.get_meta(quest_id) == true:
		if player.has_method("add_treats"):
			player.add_treats(reward_treats)
		player.set_meta(quest_id, false)
		player.set_meta("%s_completed" % quest_id, true)
		return "%s: %s" % [npc_name, complete_message]
	return "%s: %s" % [npc_name, message]

func get_prompt(player: Node = null) -> String:
	var completed_key := "%s_completed" % quest_id
	var found = player != null and player.has_meta(quest_id) and player.get_meta(quest_id) == true
	var completed = player != null and player.has_meta(completed_key) and player.get_meta(completed_key) == true
	if completed:
		return ""
	if found:
		return "Press F: Return lunch bag to %s" % npc_name
	return "Press F: Talk to %s" % npc_name
