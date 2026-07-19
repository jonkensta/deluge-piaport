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
 */

Ext.ns('Deluge.ux.preferences');

/**
 * @class Deluge.ux.preferences.PiaPortPage
 * @extends Ext.Panel
 *
 * Preferences page: editable settings + a live status panel. onApply() is called
 * by Deluge's Preferences window on Apply/OK and pushes the settings to the core
 * plugin via deluge.client.piaport.set_config (IMPLEMENTATION_PLAN.md sections 5, 7).
 */
Deluge.ux.preferences.PiaPortPage = Ext.extend(Ext.Panel, {
    title: _('PiaPort'),
    header: false,
    border: false,
    layout: 'form',
    autoScroll: true,

    // Set true once the current config has been loaded into the form. Guards
    // onApply() from clobbering the stored config with defaults if the framework
    // applies a page the user never opened/populated.
    _loaded: false,

    initComponent: function () {
        Deluge.ux.preferences.PiaPortPage.superclass.initComponent.call(this);

        var settings = this.add({
            xtype: 'fieldset',
            title: _('Settings'),
            border: false,
            autoHeight: true,
            labelWidth: 160,
            defaultType: 'textfield',
            style: 'margin-bottom: 6px;',
        });
        this.enabled = settings.add({
            xtype: 'checkbox',
            name: 'enabled',
            hideLabel: true,
            boxLabel: _('Enable automatic port updates'),
        });
        this.gluetunUrl = settings.add({
            fieldLabel: _('Gluetun control URL'),
            name: 'gluetun_url',
            width: 220,
        });
        this.apiKey = settings.add({
            fieldLabel: _('Gluetun API key'),
            name: 'api_key',
            inputType: 'password',
            width: 220,
        });
        this.clearApiKey = settings.add({
            xtype: 'checkbox',
            name: 'clear_api_key',
            hideLabel: true,
            boxLabel: _('Clear stored key'),
            hidden: true,
        });
        this.pollInterval = settings.add({
            xtype: 'spinnerfield',
            fieldLabel: _('Poll interval (seconds)'),
            name: 'poll_interval',
            width: 70,
            minValue: 30,
            maxValue: 86400,
            value: 300,
        });
        this.forceReannounce = settings.add({
            xtype: 'checkbox',
            name: 'force_reannounce',
            hideLabel: true,
            boxLabel: _('Force reannounce after a port change'),
        });
        this.setRandomPortFalse = settings.add({
            xtype: 'checkbox',
            name: 'set_random_port_false',
            hideLabel: true,
            boxLabel: _("Also disable Deluge's random port"),
        });

        var status = this.add({
            xtype: 'fieldset',
            title: _('Status'),
            border: false,
            autoHeight: true,
            labelWidth: 160,
            defaultType: 'displayfield',
        });
        this.stForwarded = status.add({ fieldLabel: _('Forwarded port (gluetun)'), value: '-' });
        this.stListen = status.add({ fieldLabel: _('Deluge listen port'), value: '-' });
        this.stPf = status.add({ fieldLabel: _('Port forwarding'), value: '-' });
        this.stRunning = status.add({ fieldLabel: _('Polling'), value: '-' });
        this.stChecked = status.add({ fieldLabel: _('Last checked'), value: '-' });
        this.stSuccess = status.add({ fieldLabel: _('Last success'), value: '-' });
        this.stError = status.add({ fieldLabel: _('Last error'), value: '-' });
        this.checkBtn = status.add({
            xtype: 'button',
            text: _('Check now'),
            handler: this.onCheckNowClick,
            scope: this,
            style: 'margin-top: 6px; margin-left: 165px;',
        });

        // Load config once when the page first renders; refresh status whenever it
        // becomes visible.
        this.on('render', this.onPageRender, this);
        this.on('activate', this.updateStatus, this);
    },

    onPageRender: function () {
        this.updateConfig();
        this.updateStatus();
    },

    updateConfig: function () {
        deluge.client.piaport.get_config({
            success: function (config) {
                this.enabled.setValue(config.enabled);
                this.gluetunUrl.setValue(config.gluetun_url);
                this.pollInterval.setValue(config.poll_interval);
                this.forceReannounce.setValue(config.force_reannounce);
                this.setRandomPortFalse.setValue(config.set_random_port_false);

                // Never populate the key field from the server; only reflect
                // whether one is stored, and offer "Clear" only when it is. Set
                // emptyText before clearing the value so setValue can't re-apply a
                // stale placeholder.
                this.apiKey.emptyText = config.api_key_set
                    ? _('(key stored - leave blank to keep)')
                    : _('(no key set)');
                this.apiKey.setValue('');
                if (this.apiKey.rendered) {
                    this.apiKey.applyEmptyText();
                }
                this.clearApiKey.setValue(false);
                this.clearApiKey.setVisible(config.api_key_set);

                this._loaded = true;
            },
            scope: this,
        });
    },

    applyStatus: function (status) {
        var enc = Ext.util.Format.htmlEncode;
        var orDash = function (v) {
            return v === null || v === undefined || v === '' ? '-' : enc(String(v));
        };
        this.stForwarded.setValue(orDash(status.forwarded_port));
        this.stListen.setValue(orDash(status.listen_port));
        this.stPf.setValue(orDash(status.port_forwarding));
        this.stRunning.setValue(status.running ? _('yes') : _('no'));
        this.stChecked.setValue(orDash(status.last_checked));
        this.stSuccess.setValue(orDash(status.last_success));
        this.stError.setValue(orDash(status.last_error));
    },

    updateStatus: function () {
        deluge.client.piaport.get_status({
            success: this.applyStatus,
            scope: this,
        });
    },

    onCheckNowClick: function () {
        this.checkBtn.setDisabled(true);
        deluge.client.piaport.check_now({
            // check_now resolves to the fresh status dict.
            success: function (status) {
                this.applyStatus(status);
                this.checkBtn.setDisabled(false);
            },
            failure: function () {
                this.checkBtn.setDisabled(false);
            },
            scope: this,
        });
    },

    onApply: function () {
        // Don't overwrite stored config from a page the user never populated.
        if (!this._loaded) {
            return;
        }
        var config = {
            enabled: this.enabled.getValue(),
            gluetun_url: this.gluetunUrl.getValue(),
            poll_interval: Number(this.pollInterval.getValue()),
            force_reannounce: this.forceReannounce.getValue(),
            set_random_port_false: this.setRandomPortFalse.getValue(),
        };
        // api-key protocol (IMPLEMENTATION_PLAN.md section 7): clear wins; otherwise
        // a non-empty value replaces, and blank means keep (omit the field).
        if (this.clearApiKey.getValue()) {
            config.clear_api_key = true;
        } else {
            var key = this.apiKey.getValue();
            if (key) {
                config.api_key = key;
            }
        }
        deluge.client.piaport.set_config(config, {
            success: function () {
                this.apiKey.setValue('');
                this.updateConfig();
                this.updateStatus();
            },
            scope: this,
        });
    },

    onOk: function () {
        this.onApply();
    },
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
