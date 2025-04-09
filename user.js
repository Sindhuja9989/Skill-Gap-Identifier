const mongoose = require("mongoose");

const userSchema = mongoose.Schema({
    username: {
        type: String,
        required: true,
        unique: true,
        trim: true,
        maxLength: 50
    },
    password: {
        type: String,
        required: true,

    },
    email: {
        type: String,
        required: true,
        unique: true
    },
    Jobrole:{
        type:String,
        required:true
    }
});
    const Users = mongoose.model("Users", userSchema);