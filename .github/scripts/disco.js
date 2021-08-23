#!/usr/bin/env node

// Disco is like disco. 🥳 👯‍️
// Like, disable your brain and have fun!
//
// But what it does? Well, login to Discord and send a message.
// So, configure, lean back and prepare to go to the Disco.
//
// :: github.com/topscoder

//# Required libs
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth')
puppeteer.use(StealthPlugin())


//# Some settings
const discord_channel_url = process.env.DISCORD_CHANNEL_URL
const discord_username = process.env.DISCORD_USERNAME
const discord_password = process.env.DISCORD_PASSWORD
const the_message = process.env.DISCORD_MESSAGE
const discord_textbox_selector = process.env.DISCORD_TEXTBOX_SELECTOR
// True if it should run in an invisible browser window. False to see all magic happen.
// Use only at local testing.
const headless = true;


//# Let's dance!
(async () => {
    const browser = await puppeteer.launch({
        headless: headless
    });
    const page = await browser.newPage();
    await page.goto('https://discord.com/login', {
        waitUntil: 'networkidle2',
    })

    // login
    await page.type('input[name=email]', discord_username);
    await page.type('input[name=password]', discord_password);

    await page.evaluate(() => {
        document.querySelector('button[type=submit]').click();
    });

    // wait for 3 seconds. We are not in a hurry
    await page.waitForTimeout(3000);

    // check if login is successful
    if (page.url().includes('discord.com/login')) {
        console.log('Sorry, but failed to log in.')
        await browser.close();
        exit()
    }

    // enter target discord server/channel
    await page.goto(discord_channel_url, {
        waitUntil: 'networkidle2',
    })

    await page.type(discord_textbox_selector, the_message)
    await page.waitForTimeout(2000); // wait for 2 seconds
    await (await page.$(discord_textbox_selector)).press('Enter');

    // and let's dance! 👯‍♀️
    await page.waitForTimeout(3000); // wait for 3 seconds
    await browser.close();
  })();
