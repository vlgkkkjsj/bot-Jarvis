import discord

class ConfirmActionView(discord.ui.View):
    def __init__(self, interaction, action_label: str, action_callback, cancel_label="❌ Cancelar"):
        super().__init__(timeout=30)
        self.interaction = interaction
        self.action_callback = action_callback

        self.add_item(discord.ui.Button(label=action_label, style=discord.ButtonStyle.danger, custom_id="confirm_action"))
        self.add_item(discord.ui.Button(label=cancel_label, style=discord.ButtonStyle.secondary, custom_id="cancel_action"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.interaction.user:
            await interaction.response.send_message("❌ Apenas quem iniciou o comando pode usar estes botões.", ephemeral=True)
            return False
        return True


    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.interaction.response.is_done():
            await self.interaction.edit_original_response(view=self)

    async def on_item_interaction(self, interaction: discord.Interaction, item: discord.ui.Item):
        if item.custom_id == "confirm_action":
            await self.action_callback(interaction)
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)
            self.stop()
        elif item.custom_id == "cancel_action":
            await interaction.response.edit_message(content="❌ Ação cancelada.", view=None)
            self.stop()
