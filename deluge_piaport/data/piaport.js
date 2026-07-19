/**
 * piaport.js
 *
 * Copyright (C) 2026 Jonathan Starr
 *
 * Plugin structure based on Deluge's built-in Label plugin (label.js).
 *
 * Licensed under GNU General Public License 3.0, or later, with the additional
 * special exception to link portions of this program with the OpenSSL library.
 * See LICENSE for more details.
 *
 * SCAFFOLD (milestone 1): registers the plugin and a placeholder Preferences page.
 * The editable settings form, live status panel, "Check now" button, and the
 * onApply() -> deluge.client.piaport.set_config wiring land in milestone 4 -- see
 * IMPLEMENTATION_PLAN.md sections 5 and 7.
 */

Ext.ns('Deluge.ux.preferences');

/**
 * @class Deluge.ux.preferences.PiaPortPage
 * @extends Ext.Panel
 */
Deluge.ux.preferences.PiaPortPage = Ext.extend(Ext.Panel, {
    title: _('PiaPort'),
    layout: 'fit',
    border: false,

    initComponent: function () {
        Deluge.ux.preferences.PiaPortPage.superclass.initComponent.call(this);
        this.fieldset = this.add({
            xtype: 'fieldset',
            border: false,
            title: _('PiaPort'),
            autoHeight: true,
            labelWidth: 1,
            defaultType: 'panel',
        });
        this.fieldset.add({
            border: false,
            bodyCfg: {
                html: _(
                    '<p>The PiaPort plugin is enabled.</p><br>' +
                        '<p>Settings and live status will appear here.</p>'
                ),
            },
        });
    },

    // TODO(milestone 4): implement onApply() to gather the settings form values
    // and call deluge.client.piaport.set_config(...) with the api-key protocol.
});

Ext.ns('Deluge.plugins');

/**
 * @class Deluge.plugins.PiaPortPlugin
 * @extends Deluge.Plugin
 */
Deluge.plugins.PiaPortPlugin = Ext.extend(Deluge.Plugin, {
    name: 'PiaPort',

    onDisable: function () {
        deluge.preferences.removePage(this.prefsPage);
    },

    onEnable: function () {
        this.prefsPage = deluge.preferences.addPage(
            new Deluge.ux.preferences.PiaPortPage()
        );
    },
});

Deluge.registerPlugin('PiaPort', Deluge.plugins.PiaPortPlugin);
