extends Control

@onready var score_label: Label = %ScoreLabel
@onready var click_button: TextureButton = %ClickButton
@onready var click_label: Label = %ClickLabel
@onready var particles: CPUParticles2D = %ClickParticles
@onready var upgrade_container: VBoxContainer = %UpgradeContainer
@onready var per_sec_label: Label = %PerSecLabel

var score: float = 0.0
var click_power: int = 1
var income_per_second: float = 0.0

var upgrades: Array[Dictionary] = [
	{
		"name": "Auto Clicker",
		"base_cost": 10,
		"income": 0.1,
		"owned": 0,
		"description": "+0.1/s",
	},
	{
		"name": "Double Click",
		"base_cost": 50,
		"income": 0.5,
		"owned": 0,
		"description": "+0.5/s",
	},
	{
		"name": "Click Farm",
		"base_cost": 250,
		"income": 2.0,
		"owned": 0,
		"description": "+2.0/s",
	},
	{
		"name": "Click Factory",
		"base_cost": 1000,
		"income": 10.0,
		"owned": 0,
		"description": "+10.0/s",
	},
	{
		"name": "Click Singularity",
		"base_cost": 5000,
		"income": 50.0,
		"owned": 0,
		"description": "+50.0/s",
	},
]

var _upgrade_buttons: Array[Button] = []


func _ready() -> void:
	_load_game()
	_build_upgrade_ui()
	_update_display()
	click_button.pressed.connect(_on_click)


func _process(delta: float) -> void:
	if income_per_second > 0.0:
		score += income_per_second * delta
		_update_display()


func _on_click() -> void:
	score += click_power
	_update_display()
	_spawn_click_feedback()
	if particles:
		particles.emitting = true


func _spawn_click_feedback() -> void:
	var popup := Label.new()
	popup.text = "+" + str(click_power)
	popup.add_theme_font_size_override("font_size", 16)
	popup.add_theme_color_override("font_color", Color(1.0, 0.9, 0.2))
	popup.position = click_button.global_position + Vector2(
		randf_range(-20, 20),
		randf_range(-30, -10)
	)
	popup.z_index = 100
	add_child(popup)

	var tween := create_tween()
	tween.tween_property(popup, "position:y", popup.position.y - 40, 0.6)
	tween.parallel().tween_property(popup, "modulate:a", 0.0, 0.6)
	tween.tween_callback(popup.queue_free)


func _build_upgrade_ui() -> void:
	for child in upgrade_container.get_children():
		child.queue_free()
	_upgrade_buttons.clear()

	for i in range(upgrades.size()):
		var upgrade := upgrades[i]
		var btn := Button.new()
		btn.custom_minimum_size = Vector2(200, 30)
		btn.pressed.connect(_buy_upgrade.bind(i))
		upgrade_container.add_child(btn)
		_upgrade_buttons.append(btn)

	_update_upgrade_buttons()


func _buy_upgrade(index: int) -> void:
	var upgrade := upgrades[index]
	var cost := _get_cost(upgrade)
	if score >= cost:
		score -= cost
		upgrade["owned"] = upgrade["owned"] as int + 1
		_recalculate_income()
		_update_display()
		_update_upgrade_buttons()
		_save_game()


func _get_cost(upgrade: Dictionary) -> float:
	var base: float = upgrade["base_cost"] as float
	var owned: int = upgrade["owned"] as int
	return floorf(base * pow(1.15, owned))


func _recalculate_income() -> void:
	income_per_second = 0.0
	for upgrade in upgrades:
		var owned: int = upgrade["owned"] as int
		var income: float = upgrade["income"] as float
		income_per_second += owned * income


func _update_display() -> void:
	score_label.text = _format_number(score)
	per_sec_label.text = _format_number(income_per_second) + "/s"
	click_label.text = "Click! (+" + str(click_power) + ")"
	_update_upgrade_buttons()


func _update_upgrade_buttons() -> void:
	for i in range(_upgrade_buttons.size()):
		var upgrade := upgrades[i]
		var cost := _get_cost(upgrade)
		var owned: int = upgrade["owned"] as int
		var btn := _upgrade_buttons[i]
		btn.text = "%s (%d) - %s" % [upgrade["name"], owned, _format_number(cost)]
		btn.disabled = score < cost


func _format_number(value: float) -> String:
	if value >= 1_000_000_000:
		return "%.1fB" % (value / 1_000_000_000)
	elif value >= 1_000_000:
		return "%.1fM" % (value / 1_000_000)
	elif value >= 1_000:
		return "%.1fK" % (value / 1_000)
	else:
		return str(int(value))


# --- Save / Load ---

const SAVE_PATH := "user://save.json"


func _save_game() -> void:
	var data := {
		"score": score,
		"click_power": click_power,
		"upgrades": [],
	}
	for upgrade in upgrades:
		data["upgrades"].append({"owned": upgrade["owned"]})

	var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(data))


func _load_game() -> void:
	if not FileAccess.file_exists(SAVE_PATH):
		return

	var file := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if not file:
		return

	var json := JSON.new()
	if json.parse(file.get_as_text()) != OK:
		return

	var data: Dictionary = json.data
	score = data.get("score", 0.0) as float
	click_power = data.get("click_power", 1) as int

	var saved_upgrades: Array = data.get("upgrades", [])
	for i in range(mini(saved_upgrades.size(), upgrades.size())):
		upgrades[i]["owned"] = saved_upgrades[i].get("owned", 0) as int

	_recalculate_income()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		_save_game()
		get_tree().quit()
