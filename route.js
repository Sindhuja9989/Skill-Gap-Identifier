const express = require('express');
const router = express.Router();
const { authMiddleware } = require('../middleware/authmiddleware');
const { Users } = require('../db/user');
const jwt = require('jsonwebtoken'); // Import jwt
const { SECRET } = process.env; // Ensure SECRET is imported from environment variables
require('dotenv').config();
const bcrypt = require('bcrypt');

router.post("/signup", async (req, res) => {
    const { username, password, email } = req.body;
    if (!username || !password || !email) {
        return res.status(400).json({ message: "Missing required fields" });
    }
    try {
        const userExists = await Users.findOne({ $or: [{ username }, { email }] });
        if (userExists) {
            return res.status(400).json({ message: "User  already exists" });
        }
        const hash = await bcrypt.hash(password, 10);
        const user = new Users({ username, email, password: hash });
        await user.save();
        const token = jwt.sign({ username, email }, SECRET, { expiresIn: '24h' }); // Set expiration
        res.json({ message: "User  registered", token });
    } catch (err) {
        console.error(err); // Log the error for debugging
        res.status(500).json({ message: "Server error" });
    }
});

router.post("/login", async (req, res) => {
    try {
        const { username, password, email } = req.body;
        if (!username || !password || !email) {
            return res.status(400).json({ message: "Missing required fields" });
        }
        const user = await Users.findOne({ username, email });
        if (!user) {
            return res.status(400).json({ message: "Invalid username or email" });
        }
        const result = await bcrypt.compare(password, user.password); // Compare with hashed password
        if (!result) {
            return res.status(400).json({ message: "Invalid password" });
        }
        const token = jwt.sign({ username, email }, SECRET, { expiresIn: '24h' }); // Set expiration
        res.json({ message: "User  logged in", token });
    } catch (err) {
        console.error(err); // Log the error for debugging
        res.status(500).json({ message: "Server error" });
    }
});

router.get('/profile', authMiddleware, (req, res) => {
    try {
        const user = req.user; // Corrected variable name
        res.json({ user });
    } catch (err) {
        console.error(err);
        res.status(500).json({ message: "Internal Server Error" });
    }
});

router.put('/updateprofile', authMiddleware, async (req, res) => {
    try {
        const { username, email } = req.body;
        const userId = req.user._id;

        const user = await Users.findById(userId);
        if (!user) {
            return res.status(404).json({ message: "User  not found" });
        }

        if (username) user.username = username;
        if (email) user.email = email;

        await user.save();
        res.json({ message: "Profile updated successfully", user });
    } catch (err) {
        console.error(err);
        res.status(500).json({ message: "Internal Server Error" });
    }
});

module.exports = router;