local wezterm = require("wezterm")

wezterm.on("gui-startup", function(cmd)
	local tab, pane, window = wezterm.mux.spawn_window(cmd or {})
	local gui_window = window:gui_window()
	gui_window:perform_action(wezterm.action.ToggleFullScreen, pane)
end)

return {
	-- Visuals
	color_scheme = "Catppuccin Mocha",
	window_decorations = "RESIZE",
	animation_fps = 120,
	hide_tab_bar_if_only_one_tab = true,
	default_cursor_style = "SteadyBlock",

	-- Font
	font = wezterm.font({ family = "FiraCode Nerd Font" }),
	font_size = 12.5,

	-- Misc
	initial_rows = 40,
	initial_cols = 140,
	window_close_confirmation = "NeverPrompt",
	alternate_buffer_wheel_scroll_speed = 1,

	-- Keys
	keys = {
		{ key = "F10", action = wezterm.action.ToggleFullScreen },
		{ key = "=", mods = "CTRL", action = wezterm.action.DisableDefaultAssignment },
		{ key = "-", mods = "CTRL", action = wezterm.action.DisableDefaultAssignment },
	},
}
