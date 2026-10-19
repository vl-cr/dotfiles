--- @sync entry

return {
    entry = function()
        local hovered = cx.active.current.hovered
        if not hovered then
            return
        end

        if hovered.cha.is_dir then
            ya.emit("enter", {})
            if not rt.args.chooser_file then
                ya.emit("quit", {})
            end
        elseif rt.args.chooser_file then
            ya.emit("open", { hovered = true })
        else
            ya.emit("shell", { "${EDITOR:-vi} %h", block = true })
        end
    end,
}
